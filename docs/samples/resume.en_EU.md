# Alex Chen
_Senior AI-assisted Software Engineer_

## Personal information

- **Address**: Amsterdam, Netherlands
- **Email**: alex.chen.demo@example.com
- **Nationality**: Taiwanese
- **LinkedIn**: linkedin.com/in/alex-chen-demo
- **GitHub**: github.com/alex-chen-demo

**Target role**: Staff Software Engineer — Platform / Developer Tooling

## Profile

AI-native full-stack engineer with 7 years shipping production systems.
Ships 3× faster since adopting Claude Code + Cursor as primary pair-programmers.
Recent focus: building internal tooling that turns LLM usage into measurable
engineering outcomes.

## Work experience

**Period**: 2023-06 – present
**Occupation**: Senior Software Engineer
**Employer**: Example BV

**Key achievements**
- Designed and shipped a streaming-token gateway handling 4.2M requests/day with p99 latency of 180ms.
- Led migration of legacy monolith to a 12-service Kubernetes platform, cutting deploy time from 42 min to 6 min.
- Mentored 4 engineers on AI-assisted code review workflow, reducing PR iteration rounds by ~35%.

## Key projects
_Aggregated from Claude Code / Cursor / Copilot / git across 8 projects between 2025-09-15 and 2026-04-18 (312 AI-assisted sessions; last 30 days: 22/30 active days, longest streak 11 days). Capabilities: backend, frontend, devops, testing._

### internal-token-gateway (142 sessions · 38 active days)
_Claude Code primary driver; Go + Kubernetes + Redis._
- Built Server-Sent Events streaming proxy with adaptive backpressure — throughput doubled vs prior HTTP/1.1 implementation.
- Introduced token-bucket rate limiter with per-org overrides; eliminated 3 pages/week from upstream abuse.
- Wrote integration test harness covering 14 failure modes; previously 0 structured tests existed.

### ops-runbook-bot (68 sessions · 21 active days)
_Cursor primary driver; TypeScript + LangGraph + Slack API._
- Shipped oncall assistant that resolves 40% of P2 incidents without human paging.
- Implemented hallucination guard cross-referencing Grafana metrics before suggesting actions.

### design-system-v2 (53 sessions · 18 active days)
_Claude Code + Copilot dual-driver; React + Radix UI + Tailwind._
- Migrated 86 components to a11y-audited primitives; Lighthouse accessibility rose 74 → 97.
- Authored codemod for import rewrites; ran against 1,240 downstream usages with zero manual fix-up.

## Education

**Period**: 2015 – 2019
**Qualification**: BSc Computer Science
**Institution**: National Taiwan University

## Languages

- Mandarin Chinese (C2, native)
- English (C1, professional)
- Dutch (B1, conversational)

## Technical skills

Go, Python, TypeScript, React, Kubernetes, PostgreSQL, Redis, gRPC, OpenTelemetry, Terraform, GitHub Actions
