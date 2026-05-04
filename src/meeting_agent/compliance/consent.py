from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from meeting_agent.core.schemas import utc_now_iso

ConsentAction = Literal["notice_shown", "granted", "declined", "withdrawn"]


@dataclass(frozen=True)
class ConsentRecord:
    participant_id: str
    participant_name: str
    action: ConsentAction
    scope: str = "recording_transcription_summary"
    method: str = "manual"
    recorded_at: str = field(default_factory=utc_now_iso)
    note: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConsentLog:
    meeting_id: str
    records: list[ConsentRecord] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)

    def record(
        self,
        participant_id: str,
        participant_name: str,
        action: ConsentAction,
        *,
        scope: str = "recording_transcription_summary",
        method: str = "manual",
        note: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ConsentRecord:
        rec = ConsentRecord(
            participant_id=participant_id,
            participant_name=participant_name,
            action=action,
            scope=scope,
            method=method,
            note=note,
            metadata=metadata or {},
        )
        self.records.append(rec)
        return rec

    def latest_state(self) -> dict[str, ConsentRecord]:
        state: dict[str, ConsentRecord] = {}
        for record in self.records:
            state[record.participant_id] = record
        return state

    def has_active_consent(self, participant_id: str) -> bool:
        record = self.latest_state().get(participant_id)
        return bool(record and record.action == "granted")

    def missing_consent(self, participant_ids: list[str]) -> list[str]:
        return [pid for pid in participant_ids if not self.has_active_consent(pid)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "created_at": self.created_at,
            "records": [record.to_dict() for record in self.records],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConsentLog":
        return cls(
            meeting_id=data["meeting_id"],
            created_at=data.get("created_at", utc_now_iso()),
            records=[ConsentRecord(**record) for record in data.get("records", [])],
        )

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "ConsentLog":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def render_recording_notice(
    *,
    product_name: str = "AI Meeting Agent Community",
    retention: str = "ローカル保存。ユーザーが削除するまで保持されます。",
    purpose: str = "会議の文字起こし、議事録作成、ToDo抽出のため",
) -> str:
    return (
        f"# 録音・文字起こしに関する通知\n\n"
        f"{product_name} は、{purpose}、会議音声を録音し、文字起こしと要約を行います。\n\n"
        f"- 保存方針: {retention}\n"
        f"- 共有範囲: 会議主催者が明示的に共有した範囲\n"
        f"- 参加者は録音・文字起こしの停止または削除依頼を行えるようにしてください。\n\n"
        f"この通知は法的助言ではありません。商用利用時は対象地域の法令・社内規程を確認してください。\n"
    )
