"""Single source of truth for path resolution.

Two distinct path domains that 0.5.0 conflated (causing the #27 ROOT regression):

1. USER DATA — data/, profile.yaml, config.yaml — lives in the user's working
   directory (like git). Resolved relative to CWD, overridable via VIBE_RESUME_ROOT.
2. PACKAGE RESOURCES — bundled templates, company-profile YAML, version string —
   ship inside the installed package. Resolved relative to the package, never CWD.

Conflating them worked under editable install (package dir == work tree) but broke
the moment a wheel + console script put the package in site-packages (#27).
"""
from __future__ import annotations

import os
from pathlib import Path


def user_root() -> Path:
    """User working directory holding data/, profile.yaml, config.yaml.

    VIBE_RESUME_ROOT env var wins (tests + power users); otherwise CWD.
    Deliberately NOT derived from __file__ — the installed package location is
    unrelated to where the user keeps their résumé data.
    """
    env = os.environ.get("VIBE_RESUME_ROOT")
    return Path(env) if env else Path.cwd()
