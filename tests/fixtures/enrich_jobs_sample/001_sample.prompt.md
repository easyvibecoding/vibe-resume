You are drafting resume bullets for a software engineer, following 2026 hiring focus points.

Project: sample-project
Path: (not on disk)
Timespan: 2026-01-01T00:00 -> 2026-02-01T00:00
Sessions: 5
AI sources observed: claude-code
Detected tech stack: FastAPI, PostgreSQL
Task-category distribution: backend 60%, frontend 40%
Capability breadth (distinct categories): 2

Output strict YAML (no prose, no fences) with EXACTLY this shape:

summary: "<=150 chars English sentence stating role + stack + outcome>"
role_label: "<2-5 word role tag>"
achievements:
  - "<XYZ bullet, English, <=120 chars>"
tech_stack:
  - "<normalized tech name>"
keywords_for_ats:
  - "<ATS keyword>"

(This is a TRUNCATED snippet — the live emitter writes the full `_build_prompt` body which includes anti-prompt-injection wrappers, locale rules, etc. The fixture exists to show the file SHAPE, not as a verbatim copy.)
