#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "== Public Unlock Preflight =="
echo "This script verifies that publication is still intentionally on HOLD."
echo

echo "== Policy check =="
python - <<'PY'
import json
from pathlib import Path

p = Path("configs/publication_policy.json")
data = json.loads(p.read_text())

allowed = data.get("public_oss_announcement_allowed")
blocked = set(data.get("blocked_modes", []))

print("public_oss_announcement_allowed:", allowed)
print("current_stage:", data.get("current_stage"))
print("target_public_stage:", data.get("target_public_stage"))
print("blocked_modes:", ", ".join(sorted(blocked)))

assert allowed is False, "Publication appears unlocked. Stop and review intentionally."
assert "public_github_repository" in blocked, "public_github_repository is not blocked."
assert "sns_announcement" in blocked, "sns_announcement is not blocked."

print("OK: publication remains intentionally blocked")
PY

echo
echo "== Unsafe tracked files =="
git ls-files | grep -Ei '\.(wav|mp3|m4a|flac|aac)$' && {
  echo "ERROR: raw audio/media tracked"
  exit 1
} || echo "OK: no tracked audio/media"

git ls-files | grep -E '(^|/)(mic_alpha_live|mic_minutes_live|asr_minutes_faster_whisper|real_mac_evidence|evidence_export|maintainer_dashboard|public_alpha_candidate|screenshots)/' && {
  echo "ERROR: generated evidence/review directories tracked"
  exit 1
} || echo "OK: no tracked generated evidence dirs"

git ls-files | grep -Ei '(__pycache__|\.pyc$|\.pyo$|(^|/)\._|\.DS_Store$)' && {
  echo "ERROR: cache or macOS metadata tracked"
  exit 1
} || echo "OK: no tracked pycache/macOS metadata"

git grep -n "/Users/masaakisakamoto" && {
  echo "ERROR: personal absolute path detected"
  exit 1
} || echo "OK: no personal absolute paths"

echo
echo "== Gates =="
PYTHONPATH=src python -m meeting_agent release-check --root .
PYTHONPATH=src python -m meeting_agent publication-gate --root .

echo
echo "== Preflight decision =="
echo "Controlled technical review: GO"
echo "Public Alpha Candidate: GO"
echo "Public release unlock: HOLD"
