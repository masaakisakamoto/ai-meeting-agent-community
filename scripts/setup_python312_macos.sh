#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v python3.12 >/dev/null 2>&1; then
  echo "python3.12 is not installed. On macOS, install with: brew install python@3.12"
  exit 1
fi

VENV_DIR="${AI_MEETING_AGENT_VENV:-$HOME/.venvs/ai-meeting-agent-312}"

python3.12 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

python -m pip install -U pip setuptools wheel
python -m pip install -e ".[audio]"

PYTHONPATH=src python -m meeting_agent dev-env-doctor --root . --out-json dev_environment.json --out-md dev_environment.md
PYTHONPATH=src python -m meeting_agent microphone-doctor --out-json mic_doctor.json --out-md mic_doctor.md

echo "Python 3.12 audio environment created at: $VENV_DIR"
echo "Activate with: source \"$VENV_DIR/bin/activate\""
