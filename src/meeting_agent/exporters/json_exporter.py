from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from meeting_agent.core.schemas import to_dict


def write_json(obj: Any, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_dict(obj), ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
