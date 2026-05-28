"""Profile-derived name/email redaction (#24)."""
from __future__ import annotations

import re

from core.privacy import derive_profile_redactors


def test_derive_includes_full_name_and_tokens():
    pats = derive_profile_redactors({"name": "Alice Smith"})
    assert any(re.search(p, "Alice Smith") for p in pats)
    assert any(re.search(p, "Alice") for p in pats)
    assert any(re.search(p, "Smith") for p in pats)


def test_derive_includes_email_and_user_part():
    pats = derive_profile_redactors({"email": "alice.smith@example.com"})
    assert any(re.search(p, "alice.smith@example.com") for p in pats)
    assert any(re.search(p, "alice.smith") for p in pats)


def test_derive_handles_locale_name_variants():
    pats = derive_profile_redactors({"name": "Alice", "name_zh_TW": "愛麗絲"})
    assert any(re.search(p, "愛麗絲") for p in pats)


def test_derive_merges_base_patterns():
    pats = derive_profile_redactors({"name": "Bob"}, base_patterns=[r"ACME Corp"])
    assert any("ACME" in p for p in pats)


def test_derive_dedups():
    pats = derive_profile_redactors({"name": "Bob"}, base_patterns=[re.escape("Bob")])
    bob_count = sum(1 for p in pats if p == re.escape("Bob"))
    assert bob_count == 1
