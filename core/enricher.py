"""LLM enrichment using Claude Code CLI in headless mode.

For each ProjectGroup we build a compact prompt and ask `claude -p` to emit
structured YAML: summary + achievements + tech_stack refinements.
If `claude` is missing, fall back to a naive rule-based summary.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import orjson
import yaml
from rich.console import Console

from core.aggregator import GROUPS_PATH, load_groups
from core.schema import ProjectGroup
from render.i18n import get_locale

console = Console()


# Two shapes of bullet writing — pick by locale style.
PROMPT_TEMPLATE_XYZ = """You are drafting resume bullets for a software engineer, following 2026 hiring focus points:

- Google XYZ formula: "Accomplished [X] as measured by [Y], by doing [Z]" — every bullet should have a metric when possible (latency ms, % improvement, user count, cost saved, time cut).
- Frame AI tools as productivity multipliers, not skills. DON'T write "used Claude Code"; DO write "cut feature rollout time by ~40% by orchestrating Claude Code agent workflows".
- Show breadth across the stack: call out frontend / backend / DevOps / deployment / bug-fix / refactor / perf when the data supports it.
- Prefer architecture and system design verbs (designed, architected, integrated, deployed) over task verbs (did, worked on).
- Never fabricate numbers. If no metric exists in the raw data, omit the number and keep a qualitative outcome.

Project: {name}
Path: {path}
Timespan: {first} -> {last}
Sessions: {sessions}
AI sources observed: {sources}
Detected tech stack: {tech}
Task-category distribution: {categories}   # e.g. "backend 35%, frontend 20%, deployment 15%, bug-fix 10%"
Capability breadth (distinct categories): {breadth}

Raw activity summaries (noisy, fragmented, possibly multilingual):
{raw}

Output strict YAML (no prose, no fences) with EXACTLY this shape:

summary: "<=150 chars {lang_label} sentence stating role + stack + concrete outcome>"
role_label: "<2-5 word role tag, e.g. 'Full-stack' / 'Backend + DevOps' / 'RAG engineering' / 'UI polish'>"
achievements:
  - "<XYZ bullet, {lang_label}, <=120 chars, starts with a past-tense action verb (Designed / Refactored / Deployed / Fixed / Integrated / Optimized / Built / Migrated)>"
  - "<bullet>"
  - "<bullet>"
tech_stack:
  - "<normalized tech name>"
keywords_for_ats:
  - "<ATS keyword, e.g. 'FastAPI', 'Docker', 'RAG', 'WebSocket'>"

Rules:
- 2-4 achievements. Each distinct; cover different categories if breadth > 1.
- If sessions < 3 and there is no outcome signal: `achievements: []` and a single factual summary.
- Redact personal names, customer names, secrets.
- All output text must be in {lang_label}.
"""


PROMPT_TEMPLATE_NOUN_PHRASE = """你正在為一位軟體工程師撰寫 2026 年就業市場的履歷條目。請遵守下列規範：

- 採用「名詞片語 + 客觀事實」風格，避免過度行銷用語（如「主導一切」、「徹底顛覆」）。
- 每個 bullet 儘量包含可量化指標（毫秒延遲、% 提升、使用者數、節省成本、縮短時間）。
- 有數字才寫數字；無則省略，以質化成果陳述。
- 將 AI 工具視為生產力倍增器而非技能：不要寫「使用 Claude Code」,而寫「以 Claude Code 協作工作流將上線週期壓縮約 40%」。
- 展現跨職能廣度：前端 / 後端 / DevOps / 部署 / 錯誤修復 / 重構 / 效能 皆可視資料而點出。
- 偏好架構與系統設計類動詞(設計、整合、部署、遷移)勝過任務類動詞(負責、處理)。
- 所有輸出語言必須為 {lang_label}。技術名詞(React、FastAPI、PostgreSQL 等)保留英文原文。

專案名稱: {name}
路徑: {path}
時段: {first} -> {last}
會談次數: {sessions}
觀察到的 AI 來源: {sources}
偵測到的技術堆疊: {tech}
任務類別分布: {categories}
能力廣度 (相異類別數): {breadth}

原始活動摘要 (雜訊、片段,可能多語):
{raw}

請輸出嚴格 YAML(不加 prose 不加 code fence),結構如下:

summary: "<= 80 字 {lang_label} 單句,陳述角色 + 技術 + 具體成果>"
role_label: "<2-5 字角色標籤,**必須使用 {lang_label} 同一書寫系統**。範例:繁中='全端'/'後端 + DevOps';简中='全栈'/'后端 + DevOps';日本語='フルスタック'/'バックエンド + DevOps'/'全領域エンジニア';한국어='풀스택'/'백엔드 + DevOps';Deutsch='Full-Stack'/'Backend + DevOps';français='Full-stack'/'Backend + DevOps'。**禁止混用**(例如 lang_label=日本語 時禁止寫「全栈」「全端」等中文,必須寫片假名/漢字日語)。>"
achievements:
  - "<{lang_label} 名詞片語句,<=80 字,首字為動詞或名詞片語(設計、重構、部署、修復、整合、最佳化、建置、遷移)>"
  - "<bullet>"
  - "<bullet>"
tech_stack:
  - "<規範化技術名稱>"
keywords_for_ats:
  - "<ATS 關鍵字,例如 'FastAPI'、'Docker'、'RAG'、'WebSocket'>"

規則:
- 2-4 個 achievements。彼此區隔;若 breadth > 1 覆蓋不同類別。
- 若 sessions < 3 且無明顯成果訊號: `achievements: []` 並寫一句事實性 summary。
- 遮蔽個人姓名、客戶名稱、密碼/金鑰。
- **重要**:即使本指令使用繁體中文,實際輸出的 summary / role_label / achievements 必須使用 {lang_label}(技術名詞除外保留英文)。例如 lang_label=日本語 時請輸出日文,lang_label=Deutsch 時請輸出德文。
- **書寫系統檢查**:輸出前自我檢查每個欄位的書寫系統是否與 {lang_label} 一致。常見錯誤:lang_label=日本語 卻在 role_label/headline 出現「全栈」「全端」「后端」等中文字。日語應為「フルスタック」「バックエンド」「全領域」。lang_label=한국어 卻出現中文/日文。一旦偵測到混用,必須改寫整個欄位。
"""


_LANG_LABEL = {
    "en": "English",
    "zh": "繁體中文",
    "ja": "日本語",
    "ko": "한국어",
    "de": "Deutsch",
    "fr": "français",
}


def _pick_template(locale_meta: dict[str, Any]) -> tuple[str, str]:
    """Return (prompt_template, language_label) for the given locale."""
    style = locale_meta.get("style", "xyz")
    lang = locale_meta.get("language", "en")
    # zh_CN should say 简体中文; everything else follows the table.
    lang_label = "简体中文" if locale_meta.get("_key") == "zh_CN" else _LANG_LABEL.get(lang, "English")
    template = PROMPT_TEMPLATE_NOUN_PHRASE if style == "noun_phrase" else PROMPT_TEMPLATE_XYZ
    return template, lang_label


def _build_prompt(
    g: ProjectGroup,
    locale_meta: dict[str, Any] | None = None,
    tailor_keywords: list[str] | None = None,
) -> str:
    raw_lines: list[str] = []
    for a in g.activities[:12]:
        s = (a.summary or "").strip().replace("\n", " ")
        if s:
            raw_lines.append(f"- [{a.source.value}] {s[:200]}")
    raw = "\n".join(raw_lines) or "(no summaries available)"

    total = sum(g.category_counts.values()) or 1
    cat_line = ", ".join(
        f"{k} {v*100//total}%"
        for k, v in sorted(g.category_counts.items(), key=lambda kv: -kv[1])[:6]
    ) or "(uncategorized)"

    meta = locale_meta or get_locale("en_US")
    template, lang_label = _pick_template(meta)

    body = template.format(
        name=g.name,
        path=g.path or "(not on disk)",
        first=g.first_activity.isoformat(timespec="minutes"),
        last=g.last_activity.isoformat(timespec="minutes"),
        sessions=g.total_sessions,
        sources=", ".join(s.value for s in g.sources),
        tech=", ".join(g.tech_stack) or "(none detected)",
        categories=cat_line,
        breadth=g.capability_breadth,
        raw=raw,
        lang_label=lang_label,
    )
    if tailor_keywords:
        # Append the tailor block *after* the locale prompt so it acts as a
        # final instruction the model re-reads right before emitting YAML.
        kw_str = ", ".join(tailor_keywords[:12])
        body += (
            "\n\n"
            "Tailor hint — the target JD emphasises these keywords:\n"
            f"    {kw_str}\n"
            "If any of these genuinely describe the project activity above, surface them "
            "verbatim in at least one achievement (e.g. if `RAG` is listed and the project "
            "is a retrieval pipeline, prefer 'RAG' over a generic phrase like 'search stack'). "
            "Never invent a match that isn't supported by the raw activity.\n"
        )
    return body


def _call_claude(prompt: str, timeout: int = 180) -> str | None:
    if not shutil.which("claude"):
        return None
    try:
        r = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        console.print(f"  [yellow]claude call failed:[/yellow] {e}")
        return None
    if r.returncode != 0:
        console.print(f"  [yellow]claude exit {r.returncode}:[/yellow] {r.stderr[:200]}")
        return None
    return r.stdout.strip()


def _parse_yaml(s: str) -> dict[str, Any] | None:
    # strip code fences if present
    body = s.strip()
    if body.startswith("```"):
        body = "\n".join(body.splitlines()[1:])
    if body.endswith("```"):
        body = "\n".join(body.splitlines()[:-1])
    try:
        data = yaml.safe_load(body)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def _fallback_summary(g: ProjectGroup) -> dict[str, Any]:
    top_terms = g.tech_stack[:5] or ["general"]
    srcs = ", ".join(s.value for s in g.sources[:3])
    return {
        "summary": (
            f"Collaborated {g.total_sessions} times on {g.name} via {srcs}; "
            f"stack includes {', '.join(top_terms)}; "
            f"touched {g.capability_breadth} distinct task categories."
        ),
        # no role_label -> enricher keeps original headline from aggregator
        "achievements": [],
        "tech_stack": g.tech_stack,
    }


def enrich_groups(
    cfg: dict[str, Any],
    cache_dir: Path,
    limit: int | None = None,
    locale: str | None = None,
    tailor: str | None = None,
) -> None:
    groups = load_groups()
    if not groups:
        console.print("[yellow]no groups to enrich — run aggregate first[/yellow]")
        return

    locale_meta = get_locale(locale or cfg.get("render", {}).get("locale"))
    console.print(f"[dim]enriching in locale={locale_meta['_key']} style={locale_meta['style']}[/dim]")

    tailor_keywords: list[str] | None = None
    if tailor:
        from core.review import parse_jd_keywords

        tailor_path = Path(tailor)
        if not tailor_path.exists():
            console.print(f"[yellow]tailor file not found: {tailor_path}[/yellow]")
        else:
            tailor_keywords = parse_jd_keywords(tailor_path)
            preview = ", ".join(tailor_keywords[:8]) if tailor_keywords else "(none)"
            console.print(f"[dim]tailor keywords from {tailor_path.name}: {preview}[/dim]")

    use_llm = cfg.get("enrich", {}).get("mode") == "claude-code-agent"
    enriched: list[dict[str, Any]] = []
    n_to_enrich = limit if limit else len(groups)

    for i, g in enumerate(groups, 1):
        in_window = i <= n_to_enrich
        already_enriched = bool(g.summary) and bool(g.achievements)
        marker = "◎" if in_window else "·"
        console.print(f"[cyan]{marker}[/cyan] [{i}/{len(groups)}] {g.name}  ({g.total_sessions} acts)")

        if not in_window:
            # Outside the --limit window: keep whatever the previous run produced.
            # Only fill in a fallback summary for groups never enriched at all.
            if not already_enriched:
                parsed = _fallback_summary(g)
                g.summary = str(parsed.get("summary") or "")[:300]
            enriched.append(g.model_dump(mode="json"))
            continue

        if use_llm and g.total_sessions >= 2:
            out = _call_claude(_build_prompt(g, locale_meta, tailor_keywords=tailor_keywords))
            parsed = _parse_yaml(out) if out else None
        else:
            parsed = None
        if not parsed:
            parsed = _fallback_summary(g)

        g.summary = str(parsed.get("summary") or "")[:300]
        ach = parsed.get("achievements") or []
        if isinstance(ach, list):
            g.achievements = [str(a)[:200] for a in ach if a][:4]
        tech = parsed.get("tech_stack") or []
        if isinstance(tech, list) and tech:
            g.tech_stack = [str(t) for t in tech][:15]
        role = parsed.get("role_label")
        if role:
            old_tail = g.headline or ""
            if " / " in old_tail:
                _, _, rest = old_tail.partition(" / ")
                g.headline = f"{role} · {rest}"
            else:
                g.headline = str(role)
        kw = parsed.get("keywords_for_ats")
        merged = list(g.tech_stack or [])
        if isinstance(kw, list) and kw:
            for k in kw:
                if isinstance(k, str) and k.strip():
                    merged.append(k.strip())
        from core.tech_canonical import split_hard_skills

        hard, domain = split_hard_skills(merged)
        g.tech_stack = hard[:20]
        g.domain_tags = domain[:12]
        enriched.append(g.model_dump(mode="json"))

    GROUPS_PATH.write_bytes(orjson.dumps(enriched, option=orjson.OPT_INDENT_2))
    console.print(f"[green]✓[/green] wrote enriched groups → {GROUPS_PATH.name}")
