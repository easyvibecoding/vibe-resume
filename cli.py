"""AI-used-resume CLI entry point."""
from __future__ import annotations

import sys
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
@click.pass_context
def enrich(ctx: click.Context, limit: int | None, locale: str | None) -> None:
    """Ask Claude Code agent skill to summarize each project group."""
    from core.runner import run_enricher

    run_enricher(ctx.obj["config"], limit=limit, locale=locale)


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
@click.pass_context
def render(
    ctx: click.Context,
    format: str | None,
    tailor: str | None,
    locale: str | None,
    all_locales: bool,
) -> None:
    """Render resume draft to selected format and snapshot a version."""
    from core.runner import run_render
    from render.i18n import LOCALES

    if all_locales and locale:
        raise click.UsageError("--locale and --all-locales are mutually exclusive")

    fmt = format or ctx.obj["config"].get("render", {}).get("default_format", "md")

    if all_locales:
        console.print(f"[cyan]rendering {len(LOCALES)} locales[/cyan]")
        for key in LOCALES:
            console.print(f"\n[bold]── {key} ──[/bold]")
            run_render(ctx.obj["config"], fmt=fmt, tailor=tailor, locale=key)
    else:
        run_render(ctx.obj["config"], fmt=fmt, tailor=tailor, locale=locale)


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
            except Exception:
                n = -1
            table.add_row(f.stem, f.name, str(n))
    console.print(table)


@cli.command()
@click.option("--version", "-v", type=int, default=None, help="Review a rendered resume by version number")
@click.option("--file", "file_", default=None, help="Review a specific markdown file")
@click.option("--locale", default=None, help="Override locale (else inferred from filename)")
@click.option("--jd", default=None, help="Job description text file for keyword-echo scoring")
@click.option("--diff/--no-diff", default=True, help="Compare against the previous review of the same locale (default on)")
@click.pass_context
def review(
    ctx: click.Context,
    version: int | None,
    file_: str | None,
    locale: str | None,
    jd: str | None,
    diff: bool,
) -> None:
    """Score a rendered resume against the 8-point reviewer checklist."""
    from core.review import find_previous_review, parse_jd_keywords, review_file, write_report

    hist_dir = ROOT / (ctx.obj["config"].get("render", {}).get("output_dir") or "data/resume_history")
    if version is not None and file_:
        raise click.UsageError("pass --version or --file, not both")
    if file_:
        md_path = Path(file_)
    elif version is not None:
        matches = sorted(hist_dir.glob(f"resume_v{version:03d}*.md"))
        if not matches:
            raise click.UsageError(f"no resume file found for v{version:03d} in {hist_dir}")
        md_path = matches[0]
    else:
        # latest
        versioned = sorted(hist_dir.glob("resume_v*.md"))
        if not versioned:
            raise click.UsageError(f"no rendered resumes in {hist_dir} — run `render` first")
        md_path = versioned[-1]

    jd_keywords = parse_jd_keywords(Path(jd)) if jd else None
    report = review_file(md_path, locale_key=locale, jd_keywords=jd_keywords)
    out_dir = ROOT / "data" / "reviews"
    previous = find_previous_review(out_dir, report.source, report.locale) if diff else None
    md_out, json_out = write_report(report, out_dir, previous=previous)

    console.print(report.as_markdown(previous=previous))
    console.print(f"[cyan]wrote[/cyan] {md_out.relative_to(ROOT)}  ·  {json_out.relative_to(ROOT)}")


@cli.command("list-versions")
@click.pass_context
def list_versions(ctx: click.Context) -> None:
    """List draft versions via git log in data/resume_history."""
    from core.versioning import list_history

    for entry in list_history(ctx.obj["config"]):
        console.print(f"[cyan]{entry['version']}[/cyan]  {entry['date']}  {entry['subject']}")


@cli.command()
@click.argument("from_version")
@click.argument("to_version")
@click.pass_context
def diff(ctx: click.Context, from_version: str, to_version: str) -> None:
    """Diff two resume draft versions."""
    from core.versioning import diff_versions

    click.echo(diff_versions(ctx.obj["config"], from_version, to_version))


if __name__ == "__main__":
    cli()
