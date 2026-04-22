#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[1/4] JSON parse check"
python3 -m json.tool .claude-plugin/plugin.json >/dev/null
python3 -m json.tool .codex-plugin/plugin.json >/dev/null

echo "[2/4] Shared manifest invariants"
pytest -q \
  tests/test_skill_spec.py::test_plugin_manifest_has_required_fields \
  tests/test_skill_spec.py::test_plugin_manifests_agree_on_identity

echo "[3/4] Codex plugin publish-readiness checks"
pytest -q tests/test_skill_spec.py::test_codex_plugin_manifest_publish_readiness

echo "[4/4] Claude plugin manifest validation"
claude plugin validate .claude-plugin/plugin.json

echo
echo "Plugin E2E validation passed (Codex + Claude)."
