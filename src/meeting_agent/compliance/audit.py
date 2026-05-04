from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from meeting_agent.core.schemas import utc_now_iso


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    actor_id: str
    meeting_id: str | None = None
    target_id: str | None = None
    occurred_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditLogger:
    """Simple append-only JSONL audit log for local Community workflows.

    Production cloud deployments should replace this with an immutable/retained
    audit store, tenant isolation, and admin export controls.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: AuditEvent) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")

    def record(
        self,
        event_type: str,
        *,
        actor_id: str,
        meeting_id: str | None = None,
        target_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            actor_id=actor_id,
            meeting_id=meeting_id,
            target_id=target_id,
            metadata=metadata or {},
        )
        self.append(event)
        return event

    def read_all(self) -> list[AuditEvent]:
        return read_audit_events(self.path)


def read_audit_events(path: str | Path) -> list[AuditEvent]:
    out: list[AuditEvent] = []
    path = Path(path)
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        out.append(AuditEvent(**json.loads(line)))
    return out
