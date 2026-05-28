"""Career-level archetypes — biases enrich/review by seniority bracket.

Orthogonal to ``core/personas.py`` (reviewer role) and ``core/company_profiles.py``
(target employer). The three dimensions compose: same raw activity, different
(company, level, persona) triple → different résumé surface.

Pick a level explicitly when generating or reviewing; do not infer from YOE
alone — a 5-year senior with staff-scope ownership should be reviewed against
``staff_plus`` pitfalls, not ``mid``.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LevelArchetype:
    key: str
    label: str
    yoe_range: tuple[int, int]  # half-open [lo, hi); (10, 99) means "10 or more"
    page_budget: int  # recommended max pages (1 or 2)
    lead_signal: str  # what the first bullet of each role must convey
    bullet_density: str  # what kinds of bullets dominate
    enrich_bias: str  # injected into enrich LLM prompt
    review_tips: str  # appended to review scorecard when active


LEVELS: dict[str, LevelArchetype] = {
    "new_grad": LevelArchetype(
        key="new_grad",
        label="New Grad / Entry (0-1 YoE)",
        yoe_range=(0, 1),
        page_budget=1,
        lead_signal="Strong course / capstone / internship proof-of-ability",
        bullet_density="projects + coursework + internships + competitions",
        enrich_bias=(
            "This résumé is for a new graduate with under one year of professional "
            "experience. Lead with concrete deliverables from course projects, "
            "capstones, internships, hackathons, or Kaggle/CTF/competitive-programming "
            "placements. Quantify at the project scale (rows processed, accuracy lift, "
            "latency cut) rather than claiming business impact the candidate could not "
            "actually own. Open-source contributions and GitHub activity are hard "
            "currency at this level — name the repo and what was merged."
        ),
        review_tips=(
            "New-grad résumés get discounted for vague internship blurbs and for "
            "missing links to code. Each project needs a line about *what was built*, "
            "one metric, and a repo/demo link. Two pages is a red flag — trim to one."
        ),
    ),
    "junior": LevelArchetype(
        key="junior",
        label="Junior / IC1-2 (1-3 YoE)",
        yoe_range=(1, 3),
        page_budget=1,
        lead_signal="Owned a shipped feature end-to-end at least once",
        bullet_density="features shipped + bugs owned + on-call rotations",
        enrich_bias=(
            "This résumé is for a junior engineer with 1-3 years of experience. The "
            "lead bullet of each role must prove end-to-end feature ownership "
            "(design → code → ship → maintain), not just 'contributed to'. Surface "
            "on-call / incident participation, code-review volume, and any piece of "
            "the stack the candidate now owns outright. Bullets that only read "
            "'helped with X' or 'worked on Y' get cut at this bracket."
        ),
        review_tips=(
            "Junior résumés are filtered on whether the candidate has owned anything. "
            "Each role needs at least one 'shipped + maintained' bullet with a named "
            "system and an outcome. Avoid passive verbs ('assisted', 'helped', "
            "'participated')."
        ),
    ),
    "mid": LevelArchetype(
        key="mid",
        label="Mid / IC3-4 (3-6 YoE)",
        yoe_range=(3, 6),
        page_budget=1,
        lead_signal="Led a multi-sprint project with measurable business impact",
        bullet_density="multi-quarter projects + cross-team integration + mentorship",
        enrich_bias=(
            "This résumé is for a mid-level engineer with 3-6 years of experience. "
            "Lead bullets should describe multi-sprint or multi-quarter projects the "
            "candidate drove, crossed at least one team boundary, and moved a named "
            "business or platform metric. Mentorship of juniors, design-doc authorship, "
            "and technical scoping of ambiguous problems all count as level signal. "
            "Avoid drifting into pure tech-changelog territory — tie each major project "
            "to an outcome a non-engineer would recognise."
        ),
        review_tips=(
            "Mid-level résumés get flagged when every bullet is task-shaped (implemented, "
            "fixed, added). At this level reviewers want trajectory — scope expanding, "
            "ownership widening, mentorship appearing. At least one bullet per role "
            "should read 'drove / led / scoped', not 'built / implemented'."
        ),
    ),
    "senior": LevelArchetype(
        key="senior",
        label="Senior / IC5 (6-10 YoE)",
        yoe_range=(6, 10),
        page_budget=2,
        lead_signal="Owned a system or platform for 1+ years with named SLOs",
        bullet_density="system ownership + architectural decisions + team multipliers",
        enrich_bias=(
            "This résumé is for a senior engineer with 6-10 years of experience. Lead "
            "bullets must name the system owned (by boundary, not by tech — 'billing "
            "ingest pipeline', not 'Python service'), the SLO or scale envelope "
            "(QPS, p99, uptime, rows/day), and one architectural decision the candidate "
            "made and can defend. Multiplier signals matter as much as IC output — "
            "unblocked N engineers, reduced on-call load by X%, introduced a pattern "
            "now adopted across Y teams."
        ),
        review_tips=(
            "Senior résumés that read like a larger mid-level résumé get rejected. "
            "The reviewer is looking for system-level ownership, architectural "
            "trade-offs articulated in one line, and cross-team influence. Bullets "
            "without a named system or a defensible design choice are skipped."
        ),
    ),
    "staff_plus": LevelArchetype(
        key="staff_plus",
        label="Staff / Principal+ (10+ YoE)",
        yoe_range=(10, 99),
        page_budget=2,
        lead_signal="Influenced org-wide technical direction, with named artefacts",
        bullet_density="org-level initiatives + technical strategy + cross-org deliverables",
        enrich_bias=(
            "This résumé is for a Staff-level or Principal+ engineer with 10+ years "
            "of experience. Lead bullets must describe org-wide technical direction "
            "the candidate shaped — named RFCs authored, platforms they are the owner-"
            "of-record for, strategy documents that steered roadmap. Each role needs "
            "at least one bullet naming a cross-org initiative with business-unit-level "
            "outcome (revenue, risk reduced, talent retained). Avoid IC-task bullets — "
            "at this level they read as under-levelling."
        ),
        review_tips=(
            "Staff+ résumés are scanned for scope of influence per unit time. If the "
            "reader cannot find a named RFC, platform, or strategy doc within the "
            "first 15 seconds, the résumé is being under-pitched. Remove or merge "
            "bullets that read like mid-level tasks — they drag the level signal down."
        ),
    ),
    "research_scientist": LevelArchetype(
        key="research_scientist",
        label="Research Scientist / PhD track",
        yoe_range=(0, 99),  # orthogonal to industry YoE
        page_budget=2,
        lead_signal="Peer-reviewed publication record + reproducibility artefacts",
        bullet_density="publications + datasets + benchmarks + open-source releases",
        enrich_bias=(
            "This résumé is for a research scientist or PhD-track candidate (industry "
            "research lab, academic postdoc, or frontier-AI research org). Lead with "
            "peer-reviewed publications in named venues (NeurIPS, ICML, ICLR, ACL, "
            "CVPR, etc.), with citation counts if strong. For each contribution, "
            "name the dataset, the benchmark delta, and the reproducibility artefact "
            "(code, model weights, eval harness). Industry engineering bullets should "
            "be framed as 'research infrastructure enabling X paper', not as "
            "shipping stories."
        ),
        review_tips=(
            "Research résumés are filtered on venue + reproducibility. Publications "
            "without venue names, arXiv-only work misrepresented as peer-reviewed, "
            "or contributions lacking a code/dataset link are red flags. A two-page "
            "publication list beats a one-page industry-shaped résumé at this level."
        ),
    ),
}


def get_level(key: str | None) -> LevelArchetype | None:
    if not key:
        return None
    return LEVELS.get(key)


def list_level_keys() -> list[str]:
    return list(LEVELS.keys())


def infer_level_from_yoe(yoe: float) -> LevelArchetype:
    """Best-effort fallback when no explicit level is provided.

    Uses the half-open interval ``[lo, hi)`` of each level's ``yoe_range``.
    Does not return ``research_scientist`` — that track must be chosen
    explicitly since YoE does not distinguish it from industry IC roles.
    """
    for key in ("new_grad", "junior", "mid", "senior", "staff_plus"):
        lvl = LEVELS[key]
        lo, hi = lvl.yoe_range
        if lo <= yoe < hi:
            return lvl
    return LEVELS["staff_plus"]
