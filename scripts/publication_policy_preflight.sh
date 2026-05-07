#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
import json
import subprocess
from pathlib import Path

data = json.loads(Path("configs/publication_policy.json").read_text())
unlocked = bool(data.get("public_oss_announcement_allowed"))

if unlocked:
    print("Policy mode: public alpha unlocked")
    cmd = ["bash", "scripts/public_release_preflight.sh"]
else:
    print("Policy mode: hold")
    cmd = ["bash", "scripts/public_unlock_preflight.sh"]

raise SystemExit(subprocess.call(cmd))
PY
