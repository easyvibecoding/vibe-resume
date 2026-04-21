"""AI-used-resume CLI entry point."""
from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from core.config import load_config

console = Console()
ROOT = Path(__file__).parent


@click.group()
@click.option(
    "--config", "-c", default="config.yaml", help="Path to config.yaml", show_default=True
)
@click.pass_context
def cli(ctx: click.Context, config: str) -> None:
    """AI-used-resume: extract, enrich, render."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["config"] = load_config(config)


def _warn_if_company_stale(company_key: str | None) -> None:
    """Emit a loud staleness warning whenever ``--company <key>`` is applied.

    Both ``enrich`` and ``review`` call this right before they pass the key
    down into their respective biasers, so operators never silently tailor a
    résumé against a profile that is months out of date. The warning links
    to the refresh command (``company verify``) and the local mark-clean
    command (``company mark-verified``) so the remediation path is obvious.
    """
    if not company_key:
        return
    from core.company_profiles import days_since_verification, get_company, is_stale

    c = get_company(company_key)
    if c is None:
        # CLI caller will print its own "unknown company" notice; skip here.
        return
    if is_stale(c):
        age = days_since_verification(c)
        console.print(
            f"[red bold]⚠ company profile for '{c.key}' is {age} days old "
            f"(last verified {c.last_verified_at})[/red bold]"
        )
        console.print(
            "[yellow]run `vibe-resume company verify "
            f"{c.key}` to refresh, or "
            f"`vibe-resume company mark-verified {c.key}` if you have already "
            "confirmed the profile by hand.[/yellow]"
        )


@cli.command()
@click.option("--only", multiple=True, help="Run only specific extractors by name")
@click.pass_context
def extract(ctx: click.Context, only: tuple[str, ...]) -> None:
    """Run extractors and cache raw activities."""
    from core.runner import run_extractors

    run_extractors(ctx.obj["config"], only=list(only) if only else None)


@cli.command()
@click.pass_context
def aggregate(ctx: click.Context) -> None:
    """Group activities by project and compute stats."""
    from core.runner import run_aggregator

    run_aggregator(ctx.obj["config"])


@cli.command()
@click.option("--limit", "-n", type=int, default=None, help="Enrich top N groups only")
@click.option("--locale", default=None, help="Target locale (controls bullet language + style)")
@click.option(
    "--tailor",
    default=None,
    help="Path to JD .txt; extracted keywords are injected into the enrich prompt so achievements bias toward them",
)
@click.option(
    "--persona",
    default=None,
    help="Reviewer persona: tech_lead / hr / executive / startup_founder / academic — biases bullet phrasing toward that audience",
)
@click.option(
    "--company",
    default=None,
    help="Target employer key (see `vibe-resume company list`). Injects that company's enrich_bias into the prompt for strategic résumé tailoring.",
)
@click.option(
    "--level",
    default=None,
    help="Career level key: new_grad / junior / mid / senior / staff_plus / research_scientist — biases bullet ambition to the seniority bracket.",
)
@click.pass_context
def enrich(
    ctx: click.Context,
    limit: int | None,
    locale: str | None,
    tailor: str | None,
    persona: str | None,
    company: str | None,
    level: str | None,
) -> None:
    """Ask Claude Code agent skill to summarize each project group."""
    from core.runner import run_enricher

    _warn_if_company_stale(company)
    run_enricher(
        ctx.obj["config"],
        limit=limit,
        locale=locale,
        tailor=tailor,
        persona=persona,
        company=company,
        level=level,
    )


@cli.command()
@click.option("--format", "-f", default=None, help="md | docx | pdf | all")
@click.option("--tailor", default=None, help="Path to job description .txt to tailor for")
@click.option(
    "--locale",
    default=None,
    help="Output locale: en_US (default) | en_GB | zh_TW | zh_CN | ja_JP | de_DE | fr_FR | ko_KR",
)
@click.option(
    "--all-locales",
    is_flag=True,
    default=False,
    help="Render every supported locale in one pass (mutually exclusive with --locale)",
)
@click.option(
    "--persona",
    default=None,
    help="Reviewer persona (reads persona-scoped enrich cache; filename includes suffix). Accepts single key, comma-separated list, or 'all'.",
)
@click.pass_context
def render(
    ctx: click.Context,
    format: str | None,
    tailor: str | None,
    locale: str | None,
    all_locales: bool,
    persona: str | None,
) -> None:
    """Render resume draft to selected format and snapshot a version."""
    from core.personas import PERSONAS, list_persona_keys
    from core.runner import run_render
    from render.i18n import LOCALES

    if all_locales and locale:
        raise click.UsageError("--locale and --all-locales are mutually exclusive")

    cfg = ctx.obj["config"]
    fmt = format or cfg.get("render", {}).get("default_format", "md")

    # Expand --persona into one or more concrete keys (or [None] for default).
    if not persona:
        persona_keys: list[str | None] = [None]
    elif persona.strip().lower() == "all":
        persona_keys = list(list_persona_keys())
    else:
        raw_keys = [k.strip() for k in persona.split(",") if k.strip()]
        persona_keys = []
        for k in raw_keys:
            if k in PERSONAS:
                persona_keys.append(k)
            else:
                known = ", ".join(sorted(PERSONAS))
                console.print(f"[yellow]unknown persona '{k}'. Known: {known}[/yellow]")
        if not persona_keys:
            persona_keys = [None]

    def _render_for(locale_key: str | None, formats: list[str]) -> None:
        for p_key in persona_keys:
            if p_key:
                console.print(f"\n[bold magenta]── persona: {p_key} ──[/bold magenta]")
            for f in formats:
                run_render(cfg, fmt=f, tailor=tailor, locale=locale_key, persona=p_key)

    if all_locales:
        # If the user didn't pass --format, fan out over the configured list
        # of formats so batch runs can produce md + docx + pdf in one sweep.
        formats = [fmt] if format else cfg.get("render", {}).get("all_locales_formats") or ["md"]
        console.print(
            f"[cyan]rendering {len(LOCALES)} locale(s) × {len(persona_keys)} persona(s) × {len(formats)} format(s)[/cyan]"
        )
        for key in LOCALES:
            console.print(f"\n[bold]── {key} ──[/bold]")
            _render_for(key, formats)
    else:
        _render_for(locale, [fmt])


@cli.command("personas-compare")
@click.option(
    "--personas",
    "personas_arg",
    default=None,
    help="Comma-separated persona keys, or 'all'. Omit to diff every persona that has a cached enrich.",
)
@click.option("--limit", "-n", type=int, default=3, help="Show top-N project groups (default: 3)")
@click.pass_context
def personas_compare(ctx: click.Context, personas_arg: str | None, limit: int) -> None:
    """Side-by-side diff of persona outputs for the top project groups.

    Reads the per-persona cache files written by `enrich --persona <key>` and
    prints each group's role_label + bullets under every persona, so you can
    see whether the re-voicing actually differentiates (quality iteration).
    """
    from rich.console import Console as _C

    from core.aggregator import groups_path_for
    from core.personas import PERSONAS, list_persona_keys

    out = _C()

    # Pick which personas to show.
    if personas_arg and personas_arg.strip().lower() == "all":
        candidates = list_persona_keys()
    elif personas_arg:
        candidates = [k.strip() for k in personas_arg.split(",") if k.strip() in PERSONAS]
    else:
        # Auto-discover: every persona whose cache file actually exists.
        candidates = [k for k in list_persona_keys() if groups_path_for(k).exists()]

    if not candidates:
        raise click.UsageError(
            "no persona caches found. Run `enrich --persona tech_lead,hr,...` first, "
            "or pass --personas to point at specific keys."
        )

    # Load each persona's groups and align by project name.
    import orjson

    persona_groups: dict[str, list[dict]] = {}
    for k in candidates:
        p = groups_path_for(k)
        if not p.exists():
            out.print(f"[yellow]skip {k}: no cache at {p.name}[/yellow]")
            continue
        persona_groups[k] = orjson.loads(p.read_bytes())

    if not persona_groups:
        raise click.UsageError("no usable persona caches on disk.")

    # Use the first persona's group order as the axis (they all derive from
    # the same baseline, so ordering is stable).
    axis = next(iter(persona_groups.values()))[:limit]

    for idx, group in enumerate(axis, 1):
        name = group.get("name") or "(unnamed)"
        sessions = group.get("total_sessions", 0)
        out.print(f"\n[bold cyan]── [{idx}/{limit}] {name}  ({sessions} sessions) ──[/bold cyan]")
        for p_key in candidates:
            groups = persona_groups.get(p_key) or []
            match = next((g for g in groups if g.get("name") == name), None)
            if not match:
                out.print(f"  [dim]{p_key}: (not in cache)[/dim]")
                continue
            role = match.get("headline") or match.get("role_label") or "—"
            out.print(f"\n  [bold magenta]{p_key}[/bold magenta]  [dim]{role}[/dim]")
            summary = (match.get("summary") or "").strip()
            if summary:
                out.print(f"    [italic]{summary[:160]}[/italic]")
            for ach in (match.get("achievements") or [])[:4]:
                out.print(f"    • {ach}")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show cached activity counts by source."""
    cache_dir = ROOT / "data" / "cache"
    table = Table(title="Cached activities")
    table.add_column("Source")
    table.add_column("File")
    table.add_column("Activities", justify="right")
    import orjson

    if cache_dir.exists():
        for f in sorted(cache_dir.glob("*.json")):
            try:
                n = len(orjson.loads(f.read_bytes()))
            except (OSError, orjson.JSONDecodeError):
                n = -1
            table.add_row(f.stem, f.name, str(n))
    console.print(table)


@cli.command()
@click.option("--version", "-v", type=int, default=None, help="Review a rendered resume by version number")
@click.option("--file", "file_", default=None, help="Review a specific markdown file")
@click.option("--locale", default=None, help="Override locale (else inferred from filename)")
@click.option("--jd", default=None, help="Job description text file for keyword-echo scoring")
@click.option("--diff/--no-diff", default=True, help="Compare against the previous review of the same locale (default on)")
@click.option(
    "--persona",
    default=None,
    help="Reviewer persona: tech_lead / hr / executive / startup_founder / academic — appends persona-specific review advice",
)
@click.option(
    "--company",
    default=None,
    help="Target employer key (see `vibe-resume company list`). Appends that company's review_tips to the scorecard and notes profile staleness.",
)
@click.option(
    "--level",
    default=None,
    help="Career level key: new_grad / junior / mid / senior / staff_plus / research_scientist — appends level-specific pitfalls.",
)
@click.pass_context
def review(
    ctx: click.Context,
    version: int | None,
    file_: str | None,
    locale: str | None,
    jd: str | None,
    diff: bool,
    persona: str | None,
    company: str | None,
    level: str | None,
) -> None:
    """Score a rendered resume against the 8-point reviewer checklist."""
    from core.review import (
        find_previous_review,
        parse_jd_keywords,
        resolve_resume_path,
        review_file,
        write_report,
    )

    hist_dir = ROOT / (ctx.obj["config"].get("render", {}).get("output_dir") or "data/resume_history")
    try:
        md_path = resolve_resume_path(hist_dir, version=version, file=file_)
    except (ValueError, FileNotFoundError) as e:
        # Map domain errors to click's user-facing error type.
        raise click.UsageError(str(e)) from e

    _warn_if_company_stale(company)
    jd_keywords = parse_jd_keywords(Path(jd)) if jd else None
    report = review_file(
        md_path,
        locale_key=locale,
        jd_keywords=jd_keywords,
        persona=persona,
        company=company,
        level=level,
    )
    out_dir = ROOT / "data" / "reviews"
    previous = find_previous_review(out_dir, report.source, report.locale) if diff else None
    md_out, json_out = write_report(report, out_dir, previous=previous)

    console.print(report.as_markdown(previous=previous))
    console.print(f"[cyan]wrote[/cyan] {md_out.relative_to(ROOT)}  ·  {json_out.relative_to(ROOT)}")


@cli.command()
@click.option("--locale", default=None, help="Restrict trend to a single locale; omit to show all")
@click.pass_context
def trend(ctx: click.Context, locale: str | None) -> None:
    """Summarize review score history per locale with a sparkline."""
    from rich.table import Table

    from core.review import load_reviews_by_locale, sparkline

    reviews_dir = ROOT / "data" / "reviews"
    by_locale = load_reviews_by_locale(reviews_dir)
    if not by_locale:
        console.print(f"[yellow]no reviews found in {reviews_dir}[/yellow]")
        return

    locales = [locale] if locale else sorted(by_locale.keys())
    table = Table(title="Review score trend")
    table.add_column("Locale")
    table.add_column("Runs", justify="right")
    table.add_column("First", justify="right")
    table.add_column("Latest", justify="right")
    table.add_column("Mean", justify="right")
    table.add_column("Grade", justify="center")
    table.add_column("Trend", justify="left")

    for loc in locales:
        entries = by_locale.get(loc)
        if not entries:
            continue
        percents = [(r.total / r.max_total * 100) if r.max_total else 0 for _, r in entries]
        first = f"{entries[0][1].total}/{entries[0][1].max_total}"
        latest_v, latest_r = entries[-1]
        latest = f"v{latest_v}: {latest_r.total}/{latest_r.max_total}"
        mean = sum(percents) / len(percents)
        spark = sparkline(percents)
        table.add_row(loc, str(len(entries)), first, latest, f"{mean:.1f}%", latest_r.grade, spark)

    console.print(table)


@cli.command("list-versions")
@click.pass_context
def list_versions(ctx: click.Context) -> None:
    """List draft versions via git log in data/resume_history."""
    from core.versioning import list_history

    for entry in list_history(ctx.obj["config"]):
        console.print(f"[cyan]{entry['version']}[/cyan]  {entry['date']}  {entry['subject']}")


@cli.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
@click.option(
    "--install",
    is_flag=True,
    default=False,
    help="Append the generated snippet to the shell's rc file instead of printing it",
)
def completion(shell: str, install: bool) -> None:
    """Print (or install) a shell completion script for `vibe-resume`.

    Examples:
        vibe-resume completion zsh >> ~/.zshrc
        vibe-resume completion zsh --install
    """
    import os
    import subprocess

    # Click auto-generates completion when _<PROG_NAME>_COMPLETE=<shell>_source is set.
    env = os.environ.copy()
    env["_VIBE_RESUME_COMPLETE"] = f"{shell}_source"
    result = subprocess.run(
        ["vibe-resume"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    snippet = result.stdout.strip()
    if not snippet:
        console.print(
            f"[red]Failed to generate completion for {shell}.[/red] "
            f"Make sure `vibe-resume` is on PATH (is the project installed? "
            f"run `uv sync` or `pip install -e .`)."
        )
        raise click.exceptions.Exit(1)

    if not install:
        click.echo(snippet)
        return

    rc_path = {
        "bash": Path.home() / ".bashrc",
        "zsh": Path.home() / ".zshrc",
        "fish": Path.home() / ".config/fish/completions/vibe-resume.fish",
    }[shell]
    rc_path.parent.mkdir(parents=True, exist_ok=True)
    marker = "# >>> vibe-resume completion >>>"
    end_marker = "# <<< vibe-resume completion <<<"
    existing = rc_path.read_text() if rc_path.exists() else ""
    if marker in existing:
        console.print(f"[yellow]completion block already present in {rc_path}; leaving as-is[/yellow]")
        return
    block = f"\n{marker}\n{snippet}\n{end_marker}\n"
    with rc_path.open("a", encoding="utf-8") as fh:
        fh.write(block)
    console.print(f"[green]✓[/green] appended completion block to {rc_path}")
    console.print(f"[dim]Open a new shell or `source {rc_path}` to activate.[/dim]")


@cli.command()
@click.argument("from_version")
@click.argument("to_version")
@click.pass_context
def diff(ctx: click.Context, from_version: str, to_version: str) -> None:
    """Diff two resume draft versions."""
    from core.versioning import diff_versions

    click.echo(diff_versions(ctx.obj["config"], from_version, to_version))


# ---------------------------------------------------------------------------
# company-profile inspection / audit commands
#
# These help operators decide whether a specific profile is fresh enough to
# bias a résumé against, or whether the data has aged out of currency. They
# never call out to the network — verification work itself is a separate
# flow (subagent fact-check pass). These commands are read-only.
# ---------------------------------------------------------------------------


@cli.group()
def company() -> None:
    """Inspect and audit bundled company-review profiles."""


@company.command("list")
@click.option("--tier", default=None, help="Filter to one tier (e.g. frontier_ai, jp)")
def company_list(tier: str | None) -> None:
    """List all registered company profiles, grouped by tier."""
    from core.company_profiles import COMPANY_PROFILES, KNOWN_TIERS, list_by_tier

    target_tiers = [tier] if tier else sorted(KNOWN_TIERS)
    for t in target_tiers:
        profiles = sorted(list_by_tier(t), key=lambda p: p.key)
        if not profiles:
            if tier:
                console.print(f"[yellow]no profiles in tier {t!r}[/yellow]")
            continue
        console.print(f"\n[bold cyan]── {t} ({len(profiles)}) ──[/bold cyan]")
        for p in profiles:
            console.print(
                f"  [green]{p.key:<20}[/green] {p.label}  "
                f"[dim]({p.locale_hint}, verified {p.last_verified_at})[/dim]"
            )
    console.print(f"\n[dim]total profiles: {len(COMPANY_PROFILES)}[/dim]")


@company.command("show")
@click.argument("key")
def company_show(key: str) -> None:
    """Print one profile's full content in a human-readable layout."""
    from core.company_profiles import COMPANY_PROFILES, days_since_verification

    profile = COMPANY_PROFILES.get(key)
    if not profile:
        known = ", ".join(sorted(COMPANY_PROFILES.keys())[:20])
        raise click.UsageError(
            f"unknown company key {key!r}. First 20 known: {known}…"
        )

    age_days = days_since_verification(profile)
    age_tag = "[green]fresh[/green]" if age_days < 180 else "[red]stale[/red]"
    console.print(
        f"\n[bold]{profile.label}[/bold] "
        f"[dim]({profile.key}, {profile.tier}, {profile.locale_hint})[/dim]"
    )
    console.print(
        f"[dim]last verified: {profile.last_verified_at} "
        f"({age_days}d ago) — {age_tag}[/dim]\n"
    )

    def _section(title: str, items: tuple[str, ...]) -> None:
        console.print(f"[bold yellow]{title}[/bold yellow]")
        for it in items:
            console.print(f"  • {it}")
        console.print()

    _section("Must-haves", profile.must_haves)
    _section("Plus signals", profile.plus_signals)
    _section("Red flags", profile.red_flags)
    _section("Format rules", profile.format_rules)
    _section("Keyword anchors", profile.keyword_anchors)
    console.print("[bold yellow]Enrich bias[/bold yellow]")
    console.print(f"  {profile.enrich_bias}\n")
    console.print("[bold yellow]Review tips[/bold yellow]")
    console.print(f"  {profile.review_tips}\n")
    if profile.verification_sources:
        _section("Verification sources", profile.verification_sources)


# ---------------------------------------------------------------------------
# Verification loop — subagent fact-check + YAML date bump
#
# ``company verify`` delegates to the ``claude -p`` agent so the actual web-
# search / fetch work happens in a subprocess with the full Claude Code
# toolset; the CLI's job is to package the profile YAML into a structured
# fact-check prompt and persist the returned markdown report under
# ``data/verification_reports/`` for traceability. ``company mark-verified``
# then bumps ``last_verified_at`` after a human has reviewed the report (or
# immediately, via ``--apply``, when the verdict is ``clean``).
# ---------------------------------------------------------------------------

VERIFICATION_REPORTS_DIR = ROOT / "data" / "verification_reports"

_VERIFY_PROMPT = """\
You are fact-checking a company résumé-review profile to prevent LLM-
hallucinated content from biasing résumés. Use your web-search and web-fetch
tools (cap at ~5 queries) to verify the specific factual claims in the YAML
below.

For each non-generic claim (named products, documented hiring process,
required documents, tech-stack claims, cited culture points), decide:

- CONFIRMED — primary or reputable secondary source found (quote URL)
- STALE — weakly supported or now outdated (quote URL + caveat)
- WRONG — contradicted by evidence (quote URL + correction)

Output format — plain markdown, nothing else:

# Verification report: {key}

Verified on: {today}
Profile source: core/profiles/{key}.yaml

## Findings

- CONFIRMED: ...
- STALE: ...
- WRONG: ...

## Verdict

Emit exactly one of these lines as the final line:

- `VERDICT: clean`          — no WRONG or STALE findings; profile can bump date.
- `VERDICT: needs-update`   — WRONG or STALE findings present; list YAML edits.

YAML under review:

---
{yaml_body}
---
"""


def _parse_verdict(report_text: str) -> str:
    """Extract the machine-readable verdict line emitted by the verify agent.

    Returns one of ``"clean"``, ``"needs-update"``, or ``"unknown"`` when
    the agent's output did not contain a ``VERDICT:`` line. Strips surrounding
    whitespace and lowercases for robustness.
    """
    import re as _re

    m = _re.search(r"^VERDICT:\s*(.+?)\s*$", report_text, _re.MULTILINE | _re.IGNORECASE)
    if not m:
        return "unknown"
    return m.group(1).strip().lower()


@company.command("verify")
@click.argument("key")
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="If the agent verdict is 'clean', auto-bump last_verified_at to today.",
)
@click.option(
    "--timeout",
    type=int,
    default=300,
    help="Claude CLI timeout in seconds (default: 300).",
)
def company_verify(key: str, apply: bool, timeout: int) -> None:
    """Fact-check ``<key>``'s profile via a Claude agent and save the report.

    Spawns ``claude -p`` with a structured fact-check prompt (max ~5 web
    queries recommended to the agent), then writes the returned markdown
    report to ``data/verification_reports/<key>_<YYYY-MM-DD>.md``. Requires
    the ``claude`` binary on PATH — if missing, prints a clear instruction.
    """
    from datetime import date

    from core.company_profiles import COMPANY_PROFILES, PROFILES_DIR

    profile = COMPANY_PROFILES.get(key)
    if profile is None:
        raise click.UsageError(
            f"unknown company key {key!r}. "
            "Run `vibe-resume company list` to see available keys."
        )

    yaml_path = PROFILES_DIR / f"{key}.yaml"
    yaml_body = yaml_path.read_text(encoding="utf-8")
    today = date.today().isoformat()
    prompt = _VERIFY_PROMPT.format(key=key, today=today, yaml_body=yaml_body)

    console.print(
        f"[cyan]verifying {profile.label} ({key}) via claude -p…[/cyan] "
        "(this may take a minute)"
    )

    from core.enricher import _call_claude

    report = _call_claude(prompt, timeout=timeout)
    if not report:
        console.print(
            "[red]claude CLI unavailable or call failed. "
            "Install claude (or re-run with a longer --timeout), "
            "or mark-verified manually after a browser fact-check.[/red]"
        )
        raise click.Abort()

    VERIFICATION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = VERIFICATION_REPORTS_DIR / f"{key}_{today}.md"
    out_path.write_text(report, encoding="utf-8")
    console.print(f"[green]✓[/green] saved report to {out_path.relative_to(ROOT)}")

    verdict = _parse_verdict(report)
    console.print(f"[bold]verdict:[/bold] {verdict}")

    # Print a short preview so operators don't have to open the file to triage
    preview_lines = [line for line in report.splitlines() if line.strip()][:18]
    console.print()
    for line in preview_lines:
        console.print(f"  {line}")
    console.print()

    if verdict == "clean" and apply:
        from core.company_profiles import update_last_verified_at

        update_last_verified_at(key, today)
        console.print(
            f"[green]✓[/green] auto-applied: {key}.yaml last_verified_at → {today}"
        )
    elif verdict == "clean":
        console.print(
            "[dim]verdict clean — re-run with --apply to bump the date, "
            f"or `vibe-resume company mark-verified {key}`.[/dim]"
        )
    elif verdict == "needs-update":
        console.print(
            "[yellow]verdict needs-update — review the report, apply YAML edits "
            f"manually, then `vibe-resume company mark-verified {key}` when done."
            "[/yellow]"
        )
    else:
        console.print(
            "[yellow]verdict could not be parsed from the agent output. "
            "Review the full report before marking verified.[/yellow]"
        )


@company.command("mark-verified")
@click.argument("key")
@click.option(
    "--date",
    "date_str",
    default=None,
    help="Override the verification date (YYYY-MM-DD). Defaults to today.",
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip the confirmation prompt.",
)
def company_mark_verified(key: str, date_str: str | None, yes: bool) -> None:
    """Bump ``<key>``'s ``last_verified_at`` to today (or a given date).

    Use after a ``company verify`` run whose verdict you've confirmed, or
    after a manual web-browser fact-check. Writes only the one YAML line;
    every other field, comment, or hand-edited formatting is preserved.
    """
    from datetime import date

    from core.company_profiles import (
        COMPANY_PROFILES,
        ProfileLoadError,
        update_last_verified_at,
    )

    profile = COMPANY_PROFILES.get(key)
    if profile is None:
        raise click.UsageError(
            f"unknown company key {key!r}. "
            "Run `vibe-resume company list` to see available keys."
        )

    new_date = date_str or date.today().isoformat()
    console.print(
        f"[bold]{profile.label}[/bold] ({key})\n"
        f"  current: {profile.last_verified_at}\n"
        f"      new: {new_date}"
    )
    if not yes and not click.confirm("apply?", default=True):
        console.print("[dim]skipped.[/dim]")
        return

    try:
        path = update_last_verified_at(key, new_date)
    except ProfileLoadError as e:
        raise click.UsageError(str(e)) from e
    console.print(
        f"[green]✓[/green] {path.relative_to(ROOT)} last_verified_at → {new_date}"
    )


@company.command("audit")
@click.option(
    "--stale-days",
    type=int,
    default=None,
    help="Override the default staleness threshold (default: 180 days).",
)
@click.option(
    "--only-stale",
    is_flag=True,
    default=False,
    help="Show only profiles past the staleness threshold.",
)
def company_audit(stale_days: int | None, only_stale: bool) -> None:
    """Summarise verification ages — surface profiles needing a fact-check."""
    from datetime import date

    from core.company_profiles import (
        COMPANY_PROFILES,
        STALE_DEFAULT_DAYS,
        days_since_verification,
        stale_profiles,
    )

    threshold = stale_days if stale_days is not None else STALE_DEFAULT_DAYS
    today = date.today()

    table = Table(
        title=f"Company-profile audit — threshold {threshold} days "
        f"(today: {today.isoformat()})",
        show_lines=False,
    )
    table.add_column("key", style="green")
    table.add_column("tier", style="cyan")
    table.add_column("verified")
    table.add_column("age (d)", justify="right")
    table.add_column("status")

    profiles = sorted(
        COMPANY_PROFILES.values(),
        key=lambda p: days_since_verification(p, today),
        reverse=True,
    )

    stale_set = {p.key for p in stale_profiles(threshold, today)}
    rendered = 0
    for p in profiles:
        age = days_since_verification(p, today)
        is_stale = p.key in stale_set
        if only_stale and not is_stale:
            continue
        status = "[red]STALE[/red]" if is_stale else "[green]fresh[/green]"
        table.add_row(p.key, p.tier, p.last_verified_at, str(age), status)
        rendered += 1

    console.print(table)
    console.print(
        f"\n[dim]{rendered} shown / {len(COMPANY_PROFILES)} total — "
        f"{len(stale_set)} stale at >{threshold} days[/dim]"
    )
    if stale_set:
        console.print(
            "[yellow]run a subagent fact-check pass on the stale entries "
            "(see core/profiles/<key>.yaml) before biasing résumés against them."
            "[/yellow]"
        )


if __name__ == "__main__":
    cli()
