"""Opt-in research/market-refresh pass (#46): emit a cited-research prompt for
the user's Claude Code session, then strictly ingest the result into the #47
rubric override at data/cache/market_rubric.yaml. Never fabricates numbers."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from vibe_resume.core import rubric as _rubric
from vibe_resume.core.paths import user_root as _user_root

RESULT_NAME = "research.result.yaml"
PROMPT_NAME = "research.prompt.md"


class ResearchValidationError(ValueError):
    """Raised when an ingested research result fails the source-required gate."""


_PROMPT = """# Market-refresh research — AI-proficiency résumé rubric

You have web search. Research how engineers are *actually hired for AI/agentic
work right now* and produce a refreshed, cited rubric. Fan out across these
angles, one focused search each:

1. Recruiter / hiring-manager evaluation criteria for AI-assisted engineers.
2. Senior-vs-junior AI signals (what separates "directs AI with judgment" from
   "uses AI").
3. ATS keyword sets for AI / agentic engineering roles (2025-2026).
4. Credible impact-metric *ranges* (review round-trips, first-pass QA %,
   cycle time, token-cost %, eval task-completion) — for sanity-checking only.
5. Current yellow-flag anti-patterns (e.g. a 2024-only LangChain/Pinecone stack
   as a headline; bare tool name-dropping; unverified LLM-as-judge claims).

ADVERSARIAL VERIFICATION (required): for every claim, confirm it against at
least two credible sources (vendor engineering blogs, DORA-style reports, ATS
vendors). KILL any ungrounded hype (e.g. "AI improves productivity 80%") that
lacks a citation. Prefer primary sources.

HARD RULES:
- `refreshed_at: "{today}"`.
- `sources:` MUST be non-empty; every entry needs a `title` and a `url`. A rubric
  with no sources will be REJECTED on ingest.
- Metric ranges are for sanity-checking / flagging ONLY — never to be written as
  numbers into a résumé bullet.

Write the result as YAML to `{result_name}` next to this file, using EXACTLY the
bundled `market_rubric.yaml` schema (version, refreshed_at, source_note,
sources[], bullet_formula, agentic_keywords, ai_tool_names, human_gate_verbs,
senior_differentiators, anti_patterns, yellow_flag_patterns[kind/pattern/why],
metric_hints{{review,cost,cycle,eval}}).

Then run: `vibe-resume research --ingest`
"""


def emit_research_prompt(out_dir: Path, *, today: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / PROMPT_NAME
    path.write_text(_PROMPT.format(today=today, result_name=RESULT_NAME), encoding="utf-8")
    return path


def _validate_regexes(data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    yfs = data.get("yellow_flag_patterns")
    if not isinstance(yfs, list):
        return warnings
    kept: list[Any] = []
    for y in yfs:
        if not isinstance(y, dict) or not y.get("pattern"):
            continue
        try:
            re.compile(str(y["pattern"]))
        except re.error as e:
            warnings.append(f"dropped yellow-flag '{y.get('kind')}' — bad regex: {e}")
            continue
        kept.append(y)
    data["yellow_flag_patterns"] = kept
    return warnings


def ingest_research(result_path: Path) -> tuple[dict[str, Any], list[str]]:
    if not result_path.exists():
        raise ResearchValidationError(
            f"no {result_path.name} — run `vibe-resume research` first, then let "
            "your session do the research and write the result."
        )
    try:
        data = yaml.safe_load(result_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ResearchValidationError(f"result YAML did not parse: {e}") from e
    if not isinstance(data, dict):
        raise ResearchValidationError("result root is not a mapping")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources or not any(
        isinstance(s, dict) and s.get("url") for s in sources
    ):
        raise ResearchValidationError(
            "refusing to install an un-sourced rubric — `sources` must be a "
            "non-empty list and at least one entry must carry a url"
        )
    warnings = _validate_regexes(data)
    out = _user_root() / "data" / "cache" / "market_rubric.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    _rubric.load_rubric.cache_clear()
    return data, warnings


def staleness_note(rubric: Any, *, as_of: date | None = None) -> str | None:
    try:
        stale = rubric.is_stale(as_of=as_of)
    except Exception:
        return None
    if not stale:
        return None
    return (
        f"market rubric refreshed {rubric.refreshed_at} is stale "
        "— run `vibe-resume research` to refresh framing/keywords"
    )
