#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=src python -m meeting_agent demo --out-dir demo_out
cat demo_out/minutes.md
