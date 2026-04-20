# Security Policy

## Supported versions

Only the latest minor release is receiving security fixes.

| Version | Supported |
|---|---|
| 0.1.x   | ✅ |
| < 0.1   | ❌ |

## Reporting a vulnerability

Please **do not open a public issue** for security concerns. Instead, use
GitHub's private reporting:

1. Go to the [Security tab](https://github.com/easyvibecoding/vibe-resume/security) of this repository.
2. Click **Report a vulnerability**.
3. Describe the issue, a reproduction path, and the affected version.

You can expect an initial response within **7 days** and a fix or mitigation
plan within **30 days** for confirmed issues.

## Threat model

`vibe-resume` runs entirely on the user's machine:

- **Extractors** read local filesystem paths (`~/.claude`, `~/.cursor`, git
  repositories you point it at, ZIPs you drop into `data/imports/`).
- **Enricher** shells out to `claude` (the Claude Code CLI) in headless mode.
  No content is sent to any other network endpoint.
- **Renderer** writes files to `data/drafts/` and `data/resume_history/` only.

The main risk vectors we care about:

- **Credential leakage in drafts** — `core/privacy.py` redacts obvious
  patterns (API keys, email addresses, passwords). If you find a pattern
  it misses, please report it.
- **Path traversal** from a crafted cloud-export ZIP — extractors use
  `zipfile.ZipFile` with explicit component checks, but any bypass is a
  security issue.
- **Command injection** in the enricher prompt — prompts are passed to
  `claude -p <prompt>` via `subprocess.run(..., shell=False)`, but any
  escape route is a security issue.

## Out of scope

- Issues in the LLM output itself (hallucinated achievements, tone).
  These are quality issues — open a regular issue.
- Vulnerabilities in third-party dependencies (`pydantic`, `jinja2`, etc.)
  — those are upstream. We track them via Dependabot.
