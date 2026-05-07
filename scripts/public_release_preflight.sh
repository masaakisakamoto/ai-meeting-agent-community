#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "== Public Release Preflight =="
echo "This script verifies that Public Alpha repository publication is intentionally unlocked."
echo

echo "== Policy check =="
python - <<'PY'
import json
from pathlib import Path

p = Path("configs/publication_policy.json")
data = json.loads(p.read_text())

allowed = data.get("public_oss_announcement_allowed")
blocked = set(data.get("blocked_modes", []))
allowed_modes = set(data.get("allowed_modes", []))

print("public_oss_announcement_allowed:", allowed)
print("current_stage:", data.get("current_stage"))
print("target_public_stage:", data.get("target_public_stage"))
print("allowed_modes:", ", ".join(sorted(allowed_modes)))
print("blocked_modes:", ", ".join(sorted(blocked)))

assert allowed is True, "Publication is not unlocked."
assert data.get("current_stage") == "public_alpha", "Current stage is not public_alpha."
assert "public_github_repository" in allowed_modes, "public_github_repository is not allowed."
assert "public_github_repository" not in blocked, "public_github_repository is still blocked."
assert "commercial_landing_page" in blocked, "commercial_landing_page should remain blocked for this alpha."

print("OK: publication is intentionally unlocked for Public Alpha repository release")
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

PERSONAL_PATH_REGEX='/Users/[A-Za-z0-9._-]+'

git grep -n -E "$PERSONAL_PATH_REGEX" -- . ':(exclude).github/workflows/ci.yml' && {
  echo "ERROR: personal absolute path detected"
  exit 1
} || echo "OK: no personal absolute paths"

echo
echo "== Gates =="
PYTHONPATH=src python -m meeting_agent release-check --root .

echo
echo "== Publication gate =="
PYTHONPATH=src python - <<'PY'
from pathlib import Path
from meeting_agent.release.publication import run_publication_gate

report = run_publication_gate(Path("."))
print(report.to_json())
assert report.status == "ready", report.status
assert report.private_core_included is False
PY

echo
echo "== Preflight decision =="
echo "Controlled technical review: GO"
echo "Public Alpha repository release: GO"
echo "Production release: NO"
