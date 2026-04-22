#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[1/5] JSON parse check"
python3 -m json.tool .claude-plugin/plugin.json >/dev/null
python3 -m json.tool .claude-plugin/marketplace.json >/dev/null
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
python3 -m json.tool .codex-plugin/marketplace.json >/dev/null

echo "[2/5] Shared manifest invariants"
pytest -q \
  tests/test_skill_spec.py::test_plugin_manifest_has_required_fields \
  tests/test_skill_spec.py::test_plugin_manifests_agree_on_identity

echo "[3/5] Codex plugin publish-readiness checks"
pytest -q tests/test_skill_spec.py::test_codex_plugin_manifest_publish_readiness

echo "[4/5] Marketplace manifests installable"
pytest -q tests/test_skill_spec.py::test_marketplace_manifests_installable

echo "[5/5] Claude plugin + marketplace validation"
claude plugin validate .claude-plugin/plugin.json
claude plugin validate .claude-plugin/marketplace.json

echo
echo "Plugin E2E validation passed (Codex + Claude)."
