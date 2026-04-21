"""Reviewer-persona registry — biases enrich bullets + review advice.

Each persona captures what this reviewer-type skims for, what they discount,
and the tone that survives to the top of the résumé when they're the
expected audience.

Orthogonal to both:
- **locale** (which is language + cultural layout), and
- **--tailor <JD>** (which matches a specific job description).

Persona is the *reviewer role*, invariant of which job or language. Same
candidate résumé, same locale, same JD — but a Tech Lead vs HR vs Exec will
weight bullets differently. Run ``enrich --persona <key> --locale <L>`` per
expected audience; store each variant under its own résumé version.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    lens: str  # one-line description of what this reviewer weighs first
    enrich_bias: str  # injected into the enrich LLM prompt
    review_tips: str  # appended to the review scorecard when active


PERSONAS: dict[str, Persona] = {
    "tech_lead": Persona(
        key="tech_lead",
        label="Tech Lead / Staff+ Engineer",
        lens="System design depth, quantifiable perf/scale wins, trade-offs articulated",
        enrich_bias=(
            "This résumé will be read by a Staff+ engineer or Tech Lead. Emphasise "
            "specific architectural decisions, perf numbers (latency, throughput, p99), "
            "scale markers (req/s, rows, nodes), and concrete tech-stack depth. Name "
            "the system boundary that was crossed (Postgres → Redis, sync → async, "
            "HTTP/1.1 → streaming, monolith → N services). Avoid marketing adjectives; "
            "tech-lead readers trust numbers and specificity over superlatives."
        ),
        review_tips=(
            "Tech-lead readers skip summaries and scan bullets for: named systems, "
            "specific perf numbers, and trade-off verbs (migrated, introduced, replaced). "
            "Bullets without a metric or a named system tend to get skipped."
        ),
    ),
    "hr": Persona(
        key="hr",
        label="HR Manager / Recruiter",
        lens="Career trajectory, cross-functional collaboration, readable impact in plain language",
        enrich_bias=(
            "This résumé will be read by an HR manager or recruiter who is not a deep "
            "technical specialist. Phrase achievements in plain-language business impact "
            "first (shipped, launched, unblocked, scaled), and only then cite the enabling "
            "technology. Surface collaboration, mentorship, and ownership signals. "
            "Avoid stacks of acronyms (e.g. 'Postgres/Redis/Kafka/NATS') that block "
            "skimming — name the outcome, then one or two supporting techs."
        ),
        review_tips=(
            "HR readers bounce if the first third of the résumé is acronym soup. Lead "
            "each bullet with verb + business outcome; technology is the supporting "
            "detail, not the headline."
        ),
    ),
    "executive": Persona(
        key="executive",
        label="Executive / VP / Hiring Manager",
        lens="Business outcomes in numbers, strategic scope, team/org leverage",
        enrich_bias=(
            "This résumé will be read by an executive or VP-level hiring manager. "
            "Surface business outcomes in monetary or scale terms (revenue, cost saved, "
            "team size influenced, user reach, time-to-market). Name the problem you "
            "owned, not the stack you touched. Emphasise scope of influence (cross-team, "
            "org-wide, cross-functional) and the decision you were ultimately accountable "
            "for. The first bullet of each role should read like a business headline."
        ),
        review_tips=(
            "Executive readers want the 3-second answer: what did you own, and what did "
            "it move? Technical depth can land in a later pass — the lead bullet of "
            "each role must read as a business headline, not as a tech changelog."
        ),
    ),
    "startup_founder": Persona(
        key="startup_founder",
        label="Startup Founder / Early-stage Hiring",
        lens="End-to-end ownership, shipping velocity, resourcefulness, small-team mindset",
        enrich_bias=(
            "This résumé will be read by a startup founder hiring for an early-stage "
            "team (Series A or earlier). Emphasise end-to-end ownership (idea → ship → "
            "on-call), time-to-first-deploy, cost consciousness (no infra team? ran it "
            "on $X/mo), and willingness to own outside your formal stack. Downplay "
            "enterprise process/compliance framing. Specific shipping cadence beats "
            "abstract rigour."
        ),
        review_tips=(
            "Founder readers discount résumés that read like enterprise process. Show "
            "you shipped alone or on a tiny team, owned your own deploys, and chose "
            "cheap/fast solutions when the stakes allowed."
        ),
    ),
    "academic": Persona(
        key="academic",
        label="Academic / Research Hiring Committee",
        lens="Publications, methodology rigour, citation-worthy contribution",
        enrich_bias=(
            "This résumé will be read by an academic or research hiring committee. "
            "Emphasise methodological rigour, reproducibility (datasets, benchmarks, "
            "open source), and citation-style framing for each contribution. Frame "
            "work as a contribution to a named body of knowledge (e.g. 'extended X's "
            "Y benchmark with…') rather than as a shipping story. Call out datasets, "
            "evaluation protocols, and any peer-reviewed or preprint artefacts."
        ),
        review_tips=(
            "Academic readers look for reproducibility signals (benchmark names, "
            "dataset sizes, code + paper links) before anything else. Shipping metrics "
            "matter less than evaluation rigour and contribution-to-field framing."
        ),
    ),
}


def get_persona(key: str | None) -> Persona | None:
    if not key:
        return None
    return PERSONAS.get(key)


def list_persona_keys() -> list[str]:
    return list(PERSONAS.keys())
