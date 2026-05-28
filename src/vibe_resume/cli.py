"""AI-used-resume CLI entry point."""
from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from vibe_resume.core.config import load_config
from vibe_resume.core.paths import user_root

console = Console()
ROOT = user_root()


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
    résumé against a profile that has aged past the 90-day default (a
    quarterly refresh cadence matched to current AI-hiring market churn).
    The warning names both the refresh command (``company verify``) and
    the local mark-clean command (``company mark-verified``) so the
    remediation path is obvious without flipping back to the docs.
    """
    if not company_key:
        return
    from vibe_resume.core.company_profiles import days_since_verification, get_company, is_stale

    c = get_company(company_key)
    if c is None:
        # CLI caller will print its own "unknown company" notice; skip here.
        return
    if is_stale(c):
        age = days_since_verification(c)
        console.print(
            f"[red bold]⚠ company profile for '{c.key}' is {age} days old "
            f"(last verified {c.last_verified_at}; "
            "past the 90-day quarterly-refresh threshold)[/red bold]"
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
    from vibe_resume.core.runner import run_extractors

    run_extractors(ctx.obj["config"], only=list(only) if only else None)


@cli.command()
@click.pass_context
def aggregate(ctx: click.Context) -> None:
    """Group activities by project and compute stats."""
    from vibe_resume.core.runner import run_aggregator

    run_aggregator(ctx.obj["config"])


@cli.command()
@click.option("--limit", "-n", type=int, default=None, help="Enrich top N groups only")
@click.option("--locale", default=None, help="Target locale (controls bullet language + style)")
@click.option(
    "--tailor",
    default=None,
    help="Path to JD .txt; up to 12 keywords (tech-priority dict + capitalised fallback) "
         "are injected into the enrich prompt so achievements bias toward them. "
         "See references/tailor-keyword-extraction.md for the strategy.",
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
@click.option(
    "--mode",
    type=click.Choice(["prompt", "subprocess", "rule-based"], case_sensitive=False),
    default="prompt",
    show_default=True,
    help="prompt: emit *.prompt.md for the Claude Code session (uses subscription quota). "
         "subprocess: spawn `claude -p` (bills Agent SDK quota pool since 2026-06-15). "
         "rule-based: no LLM, fallback summaries only.",
)
@click.option(
    "--ingest",
    is_flag=True,
    default=False,
    help="Read *.yaml back from data/enrich_jobs/<persona>/<locale>/ and merge into the per-locale cache.",
)
@click.option(
    "--tailor-keywords",
    default=None,
    help="Comma-separated extra keywords always included in the tailor block (e.g. 'LangGraph,MCP,LangSmith'). "
         "Merged with --tailor extraction by default; use --tailor-keywords-strict to suppress extraction.",
)
@click.option(
    "--tailor-keywords-cap",
    type=int,
    default=12,
    show_default=True,
    help="Override the keyword cap injected into the prompt. Higher = more JD signal but more prompt tokens.",
)
@click.option(
    "--tailor-keywords-strict",
    is_flag=True,
    default=False,
    help="Use only --tailor-keywords; skip the auto-extractor entirely.",
)
@click.option(
    "--clean",
    is_flag=True,
    default=False,
    help="Clear previous *.yaml files before emitting fresh prompts (otherwise existing yaml survives a re-emit).",
)
@click.option(
    "--status",
    is_flag=True,
    default=False,
    help="Show progress across all (persona, locale) job dirs without doing anything else.",
)
@click.option(
    "--all-ready",
    is_flag=True,
    default=False,
    help="With --ingest: ingest every (persona, locale) job dir whose yaml files are all present. "
         "Skip in-progress batches.",
)
@click.option(
    "--all",
    "ingest_all",
    is_flag=True,
    default=False,
    help="With --ingest: walk every (persona, locale) under data/enrich_jobs/ and ingest each "
         "(including partially-complete batches, which fall back to rule-based summaries for "
         "missing *.yaml). Useful after a multi-persona × multi-locale emit batch.",
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
    mode: str,
    ingest: bool,
    tailor_keywords: str | None,
    tailor_keywords_cap: int,
    tailor_keywords_strict: bool,
    clean: bool,
    status: bool,
    all_ready: bool,
    ingest_all: bool,
) -> None:
    """Generate per-group résumé bullets via Claude Code session (default) or claude -p subprocess."""
    from vibe_resume.core.runner import run_enricher

    _warn_if_company_stale(company)
    run_enricher(
        ctx.obj["config"],
        limit=limit,
        locale=locale,
        tailor=tailor,
        persona=persona,
        company=company,
        level=level,
        mode=mode,
        ingest=ingest,
        ingest_all=ingest_all,
        tailor_keywords_override=tailor_keywords,
        tailor_keywords_cap=tailor_keywords_cap,
        tailor_keywords_strict=tailor_keywords_strict,
        clean=clean,
        status=status,
        all_ready=all_ready,
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
@click.option(
    "--top-n", "top_n", type=int, default=None,
    help="Number of projects rendered in full detail (rest collapse to a one-liner). Default 6 or config.render.detailed_projects.",
)
@click.pass_context
def render(
    ctx: click.Context,
    format: str | None,
    tailor: str | None,
    locale: str | None,
    all_locales: bool,
    persona: str | None,
    top_n: int | None,
) -> None:
    """Render resume draft to selected format and snapshot a version."""
    from vibe_resume.core.personas import PERSONAS, list_persona_keys
    from vibe_resume.core.runner import run_render
    from vibe_resume.render.i18n import LOCALES

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
                run_render(cfg, fmt=f, tailor=tailor, locale=locale_key, persona=p_key, top_n=top_n)

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
@click.option(
    "--locale",
    required=True,
    help="Locale of the enriched cache to compare (e.g. en_US). Required after 0.4.0 since enriched cache is per-locale.",
)
@click.pass_context
def personas_compare(ctx: click.Context, personas_arg: str | None, limit: int, locale: str) -> None:
    """Side-by-side diff of persona outputs for the top project groups.

    Reads the per-persona cache files written by `enrich --persona <key>` and
    prints each group's role_label + bullets under every persona, so you can
    see whether the re-voicing actually differentiates (quality iteration).
    """
    from rich.console import Console as _C

    from vibe_resume.core.aggregator import groups_path_for
    from vibe_resume.core.personas import PERSONAS, list_persona_keys

    out = _C()

    # Pick which personas to show.
    if personas_arg and personas_arg.strip().lower() == "all":
        candidates = list_persona_keys()
    elif personas_arg:
        candidates = [k.strip() for k in personas_arg.split(",") if k.strip() in PERSONAS]
    else:
        # Auto-discover: every persona whose cache file actually exists.
        candidates = [k for k in list_persona_keys() if groups_path_for(k, locale).exists()]

    if not candidates:
        raise click.UsageError(
            "no persona caches found. Run `enrich --persona tech_lead,hr,...` first, "
            "or pass --personas to point at specific keys."
        )

    # Load each persona's groups and align by project name.
    import orjson

    persona_groups: dict[str, list[dict]] = {}
    for k in candidates:
        p = groups_path_for(k, locale)
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


def _status_enriched(cache_dir: Path) -> None:
    import datetime as _dt
    import re

    import orjson
    from rich.table import Table as _T
    rows = []
    for f in sorted(cache_dir.glob("_project_groups.*.*.json")):
        m = re.match(r"_project_groups\.(.+)\.([a-z]{2}_[A-Z]{2})\.json$", f.name)
        if not m:
            continue
        persona, locale = m.group(1), m.group(2)
        try:
            groups = orjson.loads(f.read_bytes())
        except Exception:
            continue
        total = len(groups)
        starred = sum(1 for g in groups if g.get("achievements"))
        mtime = _dt.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
        rows.append((persona, locale, f"{total} ({starred} ★)", mtime))
    if not rows:
        console.print("[dim]no enriched caches yet[/dim]")
        return
    t = _T(title="Enriched caches")
    t.add_column("Persona")
    t.add_column("Locale")
    t.add_column("Groups")
    t.add_column("Last enriched")
    for r in rows:
        t.add_row(*r)
    console.print(t)


def _status_pending() -> None:
    from rich.table import Table as _T

    from vibe_resume.core.enrich_jobs import list_jobs
    jobs_root = ROOT / "data" / "enrich_jobs"
    jobs = list_jobs(jobs_root)
    pending = [j for j in jobs if not j["ready"]]
    if not pending:
        console.print("[dim]no pending enrich jobs[/dim]")
        return
    t = _T(title="Pending enrich jobs")
    t.add_column("Persona")
    t.add_column("Locale")
    t.add_column("Progress")
    for j in pending:
        t.add_row(j["persona"], j["locale"], f"{j['done']}/{j['total']} yaml ready")
    console.print(t)


@cli.command()
@click.option("--enriched", is_flag=True, default=False, help="Show enriched cache state per (persona, locale).")
@click.option("--pending", is_flag=True, default=False, help="Show enrich_jobs manifests with pending entries.")
@click.option("--all", "show_all", is_flag=True, default=False, help="Show raw activities + enriched + pending.")
@click.pass_context
def status(ctx: click.Context, enriched: bool, pending: bool, show_all: bool) -> None:
    """Show cached activity counts; --enriched/--pending/--all for more views."""
    cache_dir = ROOT / "data" / "cache"

    show_raw = show_all or not (enriched or pending)
    if show_raw:
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

    if enriched or show_all:
        _status_enriched(cache_dir)
    if pending or show_all:
        _status_pending()


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
    from vibe_resume.core.review import (
        find_previous_review,
        parse_jd_keywords,
        resolve_resume_path,
        review_file,
        write_report,
    )

    hist_dir = ROOT / (ctx.obj["config"].get("render", {}).get("output_dir") or "data/resume_history")
    try:
        md_path = resolve_resume_path(
            hist_dir, version=version, file=file_,
            persona=persona, locale=locale,
        )
    except (ValueError, FileNotFoundError) as e:
        # Map domain errors to click's user-facing error type.
        raise click.UsageError(str(e)) from e

    if (persona or locale) and not (version or file_):
        console.print(
            f"[dim]→ scoring {md_path.name} (matched persona={persona or '*'}, locale={locale or '*'})[/dim]"
        )

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
@click.option("--persona", default=None, help="Restrict trend to a single persona; omit to show all")
@click.option(
    "--group-by",
    default="locale,persona",
    show_default=True,
    help="Comma-separated grouping dimensions: 'locale', 'persona', or 'locale,persona'",
)
@click.pass_context
def trend(ctx: click.Context, locale: str | None, persona: str | None, group_by: str) -> None:
    """Summarize review score history per locale (and optionally persona) with a sparkline."""
    from rich.table import Table

    from vibe_resume.core.review import (
        load_reviews_by_locale,
        load_reviews_by_locale_persona,
        sparkline,
    )

    reviews_dir = ROOT / "data" / "reviews"
    dims = {d.strip() for d in group_by.split(",")}
    use_persona_dim = "persona" in dims

    if use_persona_dim:
        by_group = load_reviews_by_locale_persona(reviews_dir)
        if not by_group:
            console.print(f"[yellow]no reviews found in {reviews_dir}[/yellow]")
            return

        # apply locale / persona filters
        filtered = {
            (loc, pers): entries
            for (loc, pers), entries in by_group.items()
            if (locale is None or loc == locale)
            and (persona is None or pers == persona)
        }
        if not filtered:
            console.print(f"[yellow]no reviews matching locale={locale} persona={persona}[/yellow]")
            return

        table = Table(title="Review score trend")
        table.add_column("Locale")
        table.add_column("Persona")
        table.add_column("Runs", justify="right")
        table.add_column("First", justify="right")
        table.add_column("Latest", justify="right")
        table.add_column("Mean", justify="right")
        table.add_column("Grade", justify="center")
        table.add_column("Trend", justify="left")

        for (loc, pers), entries in sorted(
            filtered.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")
        ):
            percents = [(r.total / r.max_total * 100) if r.max_total else 0 for _, r in entries]
            first = f"{entries[0][1].total}/{entries[0][1].max_total}"
            latest_v, latest_r = entries[-1]
            latest = f"v{latest_v}: {latest_r.total}/{latest_r.max_total}"
            mean = sum(percents) / len(percents)
            spark = sparkline(percents)
            table.add_row(loc, pers or "(default)", str(len(entries)), first, latest, f"{mean:.1f}%", latest_r.grade, spark)

        console.print(table)
        return

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
    from vibe_resume.core.versioning import list_history

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
    from vibe_resume.core.versioning import diff_versions

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
    from vibe_resume.core.company_profiles import COMPANY_PROFILES, KNOWN_TIERS, list_by_tier

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
    from vibe_resume.core.company_profiles import COMPANY_PROFILES, days_since_verification

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
VERIFICATION_JOBS_DIR = ROOT / "data" / "verification_jobs"

_VERIFY_PROMPT = """\
You are fact-checking a company résumé-review profile to prevent LLM-
hallucinated content from biasing résumés. Use your web-search and web-fetch
tools (cap at ~8 queries total) to verify the specific factual claims in
the YAML below.

IMPORTANT — cross-reference BOTH timescales before classifying any claim:

1. RECENT (last ~90 days): rebrands, org/leadership shifts, interview-
   process changes, product launches or sunsets, new hiring freezes /
   mass layoffs, regulator actions. The AI hiring market moves on a
   quarterly cadence; miss a 60-day-old rebrand and the profile is
   actively misleading.
2. MULTI-YEAR (last 2-3 years): whether the claim reflects a stable
   pattern or a one-off announcement. A claim supported only by a single
   recent press release is weaker than one consistently documented
   across multiple years. Conversely, a claim supported only by
   pre-2024 sources should be marked STALE unless you can confirm it
   still holds in 2025-2026.

For each non-generic claim (named products, documented hiring process,
required documents, tech-stack claims, cited culture points, named
market verticals, language requirements), decide:

- CONFIRMED — both recent AND multi-year sources agree (quote URL and
  say which timeframe each source covers)
- STALE — only old sources support it OR a recent change has reversed
  it (quote URL + caveat + timeframe)
- WRONG — contradicted by current evidence; profile's claim is
  fabricated or was never true (quote URL + correction)

Output format — plain markdown, nothing else:

# Verification report: {key}

Verified on: {today}
Profile source: core/profiles/{key}.yaml
Timeframes queried: recent (<=90d), multi-year (2023-present)

## Findings

- CONFIRMED: <claim> — recent: <URL, summary>; historical: <URL, summary>
- STALE: <claim> — only supported by <URL, year>; no recent corroboration
- WRONG: <claim> — contradicted by <URL>; correct fact is …

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


def _handle_verdict(key: str, verdict: str, apply_flag: bool) -> None:
    """Print verdict outcome + optionally bump last_verified_at on clean+apply."""
    from datetime import date

    from vibe_resume.core.company_profiles import ProfileLoadError, update_last_verified_at

    if verdict == "clean" and apply_flag:
        try:
            path = update_last_verified_at(key, date.today().isoformat())
        except ProfileLoadError as e:
            raise click.UsageError(str(e)) from e
        console.print(
            f"[green]✓[/green] verdict clean — bumped {path.relative_to(ROOT)} "
            f"last_verified_at → today"
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


def _build_verify_prompt(key: str, profile, yaml_body: str) -> str:
    from datetime import date
    today = date.today().isoformat()
    return _VERIFY_PROMPT.format(key=key, today=today, yaml_body=yaml_body)


def _verify_emit(key, profile, profiles_dir, today, job_dir) -> None:
    import orjson

    job_dir.mkdir(parents=True, exist_ok=True)
    yaml_body = (profiles_dir / f"{key}.yaml").read_text(encoding="utf-8")
    prompt = _build_verify_prompt(key, profile, yaml_body)
    (job_dir / "prompt.md").write_text(prompt, encoding="utf-8")

    manifest = {
        "version": 1,
        "key": key, "label": profile.label,
        "created_at": today,
        "prompt": "prompt.md",
        "report": "report.md",
        "status": "pending",
    }
    (job_dir / "manifest.json").write_bytes(
        orjson.dumps(manifest, option=orjson.OPT_INDENT_2)
    )
    console.print(f"[green]✓[/green] wrote verify job to {job_dir.relative_to(ROOT)}")
    console.print(
        f"[cyan]Next:[/cyan] in your Claude Code session, run the WebSearch + WebFetch "
        f"workflow against prompt.md, save the report to {job_dir.name}/report.md, then run "
        f"`uv run vibe-resume company verify --ingest {key}`."
    )


def _verify_ingest(key: str, job_dir: Path, apply_flag: bool) -> None:
    report_path = job_dir / "report.md"
    if not report_path.exists():
        console.print(f"[red]no report.md at {report_path}[/red]")
        raise click.Abort()

    VERIFICATION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    final = VERIFICATION_REPORTS_DIR / f"{job_dir.name}.md"
    final.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[green]✓[/green] saved report to {final.relative_to(ROOT)}")

    verdict = _parse_verdict(final.read_text(encoding="utf-8"))
    _handle_verdict(key, verdict, apply_flag)


def _verify_subprocess(key, profile, profiles_dir, today, timeout, apply_flag) -> None:
    """Old 0.3.x path — kept for CI/headless."""
    from vibe_resume.core.enricher import _call_claude

    yaml_body = (profiles_dir / f"{key}.yaml").read_text(encoding="utf-8")
    prompt = _build_verify_prompt(key, profile, yaml_body)
    console.print(
        f"[cyan]verifying {profile.label} ({key}) via claude -p subprocess…[/cyan]"
    )
    report = _call_claude(prompt, timeout=timeout)
    if not report:
        console.print("[red]claude CLI unavailable or call failed.[/red]")
        raise click.Abort()

    VERIFICATION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    final = VERIFICATION_REPORTS_DIR / f"{key}_{today}.md"
    final.write_text(report, encoding="utf-8")
    console.print(f"[green]✓[/green] saved report to {final.relative_to(ROOT)}")
    verdict = _parse_verdict(report)
    _handle_verdict(key, verdict, apply_flag)


@company.command("verify")
@click.argument("key")
@click.option("--emit", "do_emit", is_flag=True, default=False,
              help="Write prompt.md + manifest.json to data/verification_jobs/<key>_<date>/ for the Claude Code session to process. Default behaviour when no --ingest or --mode subprocess.")
@click.option("--ingest", "do_ingest", is_flag=True, default=False,
              help="Read report.md from data/verification_jobs/<key>_<date>/ and save it to data/verification_reports/.")
@click.option("--mode",
              type=click.Choice(["prompt", "subprocess"], case_sensitive=False),
              default="prompt", show_default=True,
              help="prompt (default): emit + ingest pair. subprocess: spawn `claude -p` (bills Agent SDK quota pool since 2026-06-15).")
@click.option("--apply", is_flag=True, default=False,
              help="On ingest with verdict 'clean', auto-bump last_verified_at to today.")
@click.option("--timeout", type=int, default=300,
              help="claude CLI timeout in seconds (subprocess mode only).")
def company_verify(key: str, do_emit: bool, do_ingest: bool, mode: str,
                   apply: bool, timeout: int) -> None:
    """Fact-check a company profile.

    Default (prompt mode): emit prompt + manifest for the Claude Code session
    to process with WebSearch / WebFetch tools; call again with --ingest to
    save the report and parse the verdict.

    --mode subprocess: spawn `claude -p` (old 0.3.x behaviour, bills against
    Agent SDK quota pool from 2026-06-15).
    """
    from datetime import date

    from vibe_resume.core.company_profiles import COMPANY_PROFILES, PROFILES_DIR

    profile = COMPANY_PROFILES.get(key)
    if profile is None:
        raise click.UsageError(
            f"unknown company key {key!r}. Run `vibe-resume company list`."
        )

    today = date.today().isoformat()
    job_dir = VERIFICATION_JOBS_DIR / f"{key}_{today}"

    if do_ingest:
        _verify_ingest(key, job_dir, apply)
        return

    if mode == "subprocess":
        console.print(
            "[red]⚠ --mode subprocess spawns `claude -p`, billing against the "
            "Agent SDK quota pool (separate from Claude Code subscription, "
            "2026-06-15 change). Default mode 'prompt' uses your session quota.[/red]"
        )
        _verify_subprocess(key, profile, PROFILES_DIR, today, timeout, apply)
        return

    # Default = prompt mode = emit
    _verify_emit(key, profile, PROFILES_DIR, today, job_dir)


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

    from vibe_resume.core.company_profiles import (
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
    help="Override the default staleness threshold (default: 90 days — quarterly refresh cadence for the current AI hiring market).",
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

    from vibe_resume.core.company_profiles import (
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


@cli.command("run")
@click.option("--personas", default=None,
              help="Comma-separated persona keys, or 'all'. Default: default (no persona).")
@click.option("--locales", default=None,
              help="Comma-separated locale keys (e.g. en_US,zh_TW). Default: config.render.locale.")
@click.option("--tailor", default=None, help="JD .txt path (forwarded to enrich + render).")
@click.option("--level", default=None, help="Career level key (forwarded to enrich).")
@click.option("--company", default=None, help="Target company key (forwarded to enrich).")
@click.option("-n", "--limit", type=int, default=None, help="Enrich top-N groups.")
@click.option("--formats", default=None,
              help="Comma-separated render formats (md,docx,pdf). Default: config.render.all_locales_formats.")
@click.option("--max-age-days", type=int, default=7, show_default=True,
              help="If extract cache is older than this many days, run extract+aggregate first.")
@click.option("--continue", "do_continue", is_flag=True, default=False,
              help="Skip Phase A (extract+aggregate+emit); resume with ingest+render+review+trend on existing manifests.")
@click.pass_context
def run_cmd(
    ctx: click.Context,
    personas: str | None,
    locales: str | None,
    tailor: str | None,
    level: str | None,
    company: str | None,
    limit: int | None,
    formats: str | None,
    max_age_days: int,
    do_continue: bool,
) -> None:
    """Run the full pipeline (multi-persona × multi-locale) in one command.

    \b
    Phase A (default): extract + aggregate (if cache stale) + enrich emit per matrix cell.
    User then processes the emitted *.prompt.md files in their Claude Code session.

    \b
    Phase B (--continue): ingest --all + render matrix + review matrix + trend.
    No auto-dispatch; the Agent SDK quota pool is never touched.
    """
    import time

    from vibe_resume.core.personas import PERSONAS, list_persona_keys
    from vibe_resume.core.runner import run_aggregator, run_enricher, run_extractors, run_render
    from vibe_resume.render.i18n import LOCALES

    cfg = ctx.obj["config"]

    # ── Resolve persona matrix ────────────────────────────────────────────────
    if personas and personas.strip().lower() == "all":
        persona_keys: list[str | None] = list(list_persona_keys())
    elif personas:
        persona_keys = [p.strip() for p in personas.split(",") if p.strip() in PERSONAS]
        if not persona_keys:
            known = ", ".join(sorted(PERSONAS))
            raise click.UsageError(f"no valid persona keys in {personas!r}. Known: {known}")
    else:
        persona_keys = [None]

    # ── Resolve locale matrix ─────────────────────────────────────────────────
    default_locale = cfg.get("render", {}).get("locale") or "en_US"
    if locales:
        locale_keys = [loc.strip() for loc in locales.split(",") if loc.strip() in LOCALES]
        if not locale_keys:
            raise click.UsageError(f"no valid locale keys in {locales!r}.")
    else:
        locale_keys = [default_locale]

    # ── Resolve format list ───────────────────────────────────────────────────
    fmt_list = (
        [f.strip() for f in formats.split(",") if f.strip()]
        if formats
        else cfg.get("render", {}).get("all_locales_formats") or ["md"]
    )

    _warn_if_company_stale(company)

    # ════════════════════════════════════════════════════════════════════════
    # Phase B — ingest + render + review + trend
    # ════════════════════════════════════════════════════════════════════════
    if do_continue:
        console.print("[cyan]Phase B: ingest --all[/cyan]")
        run_enricher(cfg, ingest=True, ingest_all=True)

        console.print("\n[cyan]Phase B: render matrix[/cyan]")
        for loc in locale_keys:
            for p in persona_keys:
                run_render(cfg, fmt=",".join(fmt_list), tailor=tailor, locale=loc, persona=p)

        console.print("\n[cyan]Phase B: review matrix[/cyan]")
        from vibe_resume.core.review import (
            parse_jd_keywords,
            resolve_resume_path,
            review_file,
            write_report,
        )

        hist = ROOT / (cfg.get("render", {}).get("output_dir") or "data/resume_history")
        out_dir = ROOT / "data" / "reviews"
        jd_kw = parse_jd_keywords(Path(tailor)) if tailor else None
        reviewed = 0
        for loc in locale_keys:
            for p in persona_keys:
                try:
                    md_path = resolve_resume_path(hist, persona=p, locale=loc)
                except (ValueError, FileNotFoundError) as e:
                    console.print(f"  [yellow]skip review ({p or 'default'}/{loc}): {e}[/yellow]")
                    continue
                report = review_file(
                    md_path, locale_key=loc,
                    persona=p, company=company, level=level,
                    jd_keywords=jd_kw,
                )
                write_report(report, out_dir)
                reviewed += 1

        console.print(f"\n[green]✓ Phase B done.[/green] Reviewed {reviewed} file(s).")
        console.print("[dim]run `vibe-resume trend` for the sparkline summary.[/dim]")
        return

    # ════════════════════════════════════════════════════════════════════════
    # Phase A — extract + aggregate (if stale) + enrich emit per matrix cell
    # ════════════════════════════════════════════════════════════════════════
    cache_marker = ROOT / "data" / "cache" / "_project_groups.json"
    if not cache_marker.exists() or (time.time() - cache_marker.stat().st_mtime) > max_age_days * 86400:
        console.print("[cyan]Phase A: extract + aggregate (cache stale or absent)[/cyan]")
        run_extractors(cfg)
        run_aggregator(cfg)
    else:
        age_days = int((time.time() - cache_marker.stat().st_mtime) / 86400)
        console.print(
            f"[dim]skipping extract+aggregate (cache fresh, {age_days}d old)[/dim]"
        )

    n_cells = len(persona_keys) * len(locale_keys)
    console.print(
        f"\n[cyan]Phase A: emit[/cyan] {n_cells} manifest(s) "
        f"({len(persona_keys)} persona(s) × {len(locale_keys)} locale(s))"
    )
    for p in persona_keys:
        for loc in locale_keys:
            run_enricher(
                cfg,
                locale=loc,
                persona=p,
                tailor=tailor,
                level=level,
                company=company,
                limit=limit,
            )

    console.print(
        f"\n[green]✓ Phase A done.[/green] Emitted {n_cells} manifest(s). "
        "Process the *.prompt.md files in your Claude Code session, then run "
        "[cyan]`vibe-resume run --continue`[/cyan] (with the same flags) to "
        "ingest + render + review + trend."
    )


@cli.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Diagnose setup: CLI version, plugin version drift, profile/config presence."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _pkg_version

    console.print("[bold]vibe-resume doctor[/bold]\n")

    # CLI version (from installed package metadata — works in wheel installs)
    try:
        cli_version = _pkg_version("vibe-resume")
        console.print(f"[green]✓[/green] CLI version: {cli_version}")
    except PackageNotFoundError:
        cli_version = None
        console.print("[yellow]⚠[/yellow] vibe-resume not installed as a package (running from source?)")

    # Plugin manifest version (if present in this tree)
    plugin_manifest = ROOT / ".claude-plugin" / "plugin.json"
    if plugin_manifest.exists():
        import json
        try:
            pv = json.loads(plugin_manifest.read_text()).get("version")
            if cli_version and pv and pv != cli_version:
                console.print(
                    f"[yellow]⚠[/yellow] plugin.json version {pv} != CLI version {cli_version} — "
                    f"if you have both a plugin install and a work tree, align them "
                    f"(`git pull && uv sync` in the work tree)."
                )
            else:
                console.print(f"[green]✓[/green] plugin version: {pv} (in sync)")
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] plugin.json unreadable: {e}")
    else:
        console.print("[dim]·[/dim] no .claude-plugin/plugin.json in this tree (not a plugin checkout)")

    # profile.yaml / config.yaml presence
    for fname in ("profile.yaml", "config.yaml"):
        p = ROOT / fname
        if p.exists():
            console.print(f"[green]✓[/green] {fname} present")
        else:
            console.print(
                f"[yellow]⚠[/yellow] {fname} missing — run setup or copy from "
                f"{fname.replace('.yaml', '.example.yaml')}"
            )

    # data/imports/ non-sample files (privacy reminder)
    imports = ROOT / "data" / "imports"
    if imports.exists():
        extra = [f.name for f in imports.glob("*") if f.name != "sample_jd.txt" and f.is_file()]
        if extra:
            console.print(
                f"[dim]·[/dim] data/imports/ has {len(extra)} non-sample file(s): "
                f"{', '.join(extra[:3])}"
                f"{' …' if len(extra) > 3 else ''} — gitignored (only sample_jd.txt is committed), safe."
            )

    # pandoc / claude availability (optional deps)
    import shutil
    console.print(
        f"[dim]·[/dim] pandoc: {'found' if shutil.which('pandoc') else 'not found (PDF rendering disabled)'}"
    )
    console.print(
        f"[dim]·[/dim] claude CLI: {'found' if shutil.which('claude') else 'not found (--mode subprocess unavailable; default prompt mode unaffected)'}"
    )


@cli.command("jd-check")
@click.option("--tailor", required=True, help="Path to JD .txt to check coverage against.")
@click.option("--persona", default=None, help="Narrow to a persona's cache.")
@click.option("--locale", default=None, help="Narrow to a locale's cache.")
@click.option("--threshold", type=int, default=None, help="Only show keywords below this %% coverage.")
@click.pass_context
def jd_check(ctx: click.Context, tailor: str, persona: str | None, locale: str | None, threshold: int | None) -> None:
    """Report how well enriched bullets cover the JD's extracted keywords."""
    from vibe_resume.core.aggregator import load_groups
    from vibe_resume.core.review import parse_jd_keywords

    jd_path = Path(tailor)
    if not jd_path.exists():
        raise click.UsageError(f"JD file not found: {jd_path}")
    keywords = parse_jd_keywords(jd_path)
    if not keywords:
        console.print("[yellow]no keywords extracted from JD[/yellow]")
        return

    locale_key = locale or ctx.obj["config"].get("render", {}).get("locale") or "en_US"
    groups = load_groups(persona=persona, locale=locale_key)
    if not groups:
        console.print(f"[yellow]no enriched cache for (persona={persona}, locale={locale_key})[/yellow]")
        return

    total = len(groups)
    console.print(
        f"[bold]JD-Cache alignment[/bold]  JD={jd_path.name}  "
        f"cache=(persona={persona or 'default'}, locale={locale_key}), {total} groups\n"
    )

    t = Table()
    t.add_column("Keyword")
    t.add_column("Coverage", justify="right")
    t.add_column("")
    surfaced = 0
    for kw in keywords:
        hits = sum(
            1 for g in groups
            if kw.lower() in " ".join(
                [(g.summary or "")] + list(g.achievements or []) + list(g.tech_stack or [])
            ).lower()
        )
        pct = (hits * 100 // total) if total else 0
        if threshold is not None and pct >= threshold:
            continue
        mark = "✓" if hits else "✗"
        if hits:
            surfaced += 1
        t.add_row(kw, f"{hits}/{total} ({pct}%)", mark)
    console.print(t)
    console.print(
        f"\n[bold]{surfaced}/{len(keywords)}[/bold] keywords surfaced in ≥1 group; "
        f"{len(keywords) - surfaced} missing."
    )


@cli.command("review-diff")
@click.argument("va")
@click.argument("vb")
@click.option("--jd", default=None, help="JD .txt for keyword-echo scoring on both versions.")
@click.pass_context
def review_diff(ctx: click.Context, va: str, vb: str, jd: str | None) -> None:
    """Compare two résumé versions' review scorecards per-check.

    VA and VB are version numbers (e.g. 3 7) or filenames.
    """
    from vibe_resume.core.review import parse_jd_keywords, resolve_resume_path, review_file

    hist = ROOT / (ctx.obj["config"].get("render", {}).get("output_dir") or "data/resume_history")

    def _resolve(v: str) -> Path:
        if v.isdigit():
            return resolve_resume_path(hist, version=int(v))
        return Path(v)

    jd_kw = parse_jd_keywords(Path(jd)) if jd else None
    pa, pb = _resolve(va), _resolve(vb)
    ra = review_file(pa, jd_keywords=jd_kw)
    rb = review_file(pb, jd_keywords=jd_kw)

    by_name_b = {s.name: s for s in rb.scores}
    t = Table(title=f"Review diff: {pa.name} → {pb.name}")
    t.add_column("Check")
    t.add_column("A", justify="right")
    t.add_column("B", justify="right")
    t.add_column("Δ", justify="right")
    for sa in ra.scores:
        sb = by_name_b.get(sa.name)
        if sb is None:
            continue
        delta = sb.score - sa.score
        dstr = "—" if delta == 0 else (f"+{delta}" if delta > 0 else str(delta))
        t.add_row(sa.name, f"{sa.score}/{sa.max}", f"{sb.score}/{sb.max}", dstr)
    total_delta = rb.total - ra.total
    tdstr = "—" if total_delta == 0 else (f"+{total_delta}" if total_delta > 0 else str(total_delta))
    t.add_row("TOTAL", f"{ra.total}/{ra.max_total}", f"{rb.total}/{rb.max_total}", tdstr)
    console.print(t)


if __name__ == "__main__":
    cli()
