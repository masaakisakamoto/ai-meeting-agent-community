#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "== External Announcement Preflight =="
echo "This script verifies that a limited Japanese short announcement is intentionally allowed."
echo

python - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("configs/publication_policy.json").read_text())

allowed = set(data.get("allowed_modes", []))
blocked = set(data.get("blocked_modes", []))

print("current_stage:", data.get("current_stage"))
print("public_oss_announcement_allowed:", data.get("public_oss_announcement_allowed"))
print("allowed_modes:", ", ".join(sorted(allowed)))
print("blocked_modes:", ", ".join(sorted(blocked)))

assert data.get("current_stage") == "public_alpha"
assert data.get("public_oss_announcement_allowed") is True
assert "public_github_repository" in allowed
assert "sns_announcement" in allowed
assert "external_announcement_ja_short" in allowed
assert "sns_announcement" not in blocked
assert "commercial_landing_page" in blocked
assert "public_release_blog" in blocked

print("OK: limited Japanese short announcement is intentionally allowed.")
print("OK: commercial landing page and public release blog remain blocked.")
PY

echo
echo "== Safety checks =="
git ls-files | grep -Ei '\.(wav|mp3|m4a|flac|aac)$' && {
  echo "ERROR: raw audio/media tracked"
  exit 1
} || echo "OK: no tracked audio/media"

git ls-files | grep -E '(^|/)(mic_alpha_live|mic_minutes_live|asr_minutes_faster_whisper|real_mac_evidence|evidence_export|maintainer_dashboard|public_alpha_candidate|screenshots)/' && {
  echo "ERROR: generated evidence/review directories tracked"
  exit 1
} || echo "OK: no tracked generated evidence dirs"

git grep -n -E '/Users/[A-Za-z0-9._-]+' -- . ':(exclude).github/workflows/ci.yml' && {
  echo "ERROR: personal absolute path detected"
  exit 1
} || echo "OK: no personal absolute paths"

echo
echo "== Release check =="
PYTHONPATH=src python -m meeting_agent release-check --root .

echo
echo "== Decision =="
echo "Japanese short announcement: GO after final manual approval"
echo "Commercial landing page: HOLD"
echo "Public release blog: HOLD"
echo "Production release: NO"
