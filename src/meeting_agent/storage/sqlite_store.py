from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from meeting_agent.core.schemas import MinutesDraft, Transcript, minutes_from_dict, to_dict, transcript_from_dict

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
  meeting_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  transcript_json TEXT NOT NULL,
  minutes_json TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_meetings_created_at ON meetings(created_at);
"""


class SQLiteMeetingStore:
    """Tiny local-first persistence layer for demos and Community workflows."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    @contextmanager
    def _connect(self):
        con = sqlite3.connect(self.path)
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _init(self) -> None:
        with self._connect() as con:
            con.executescript(SCHEMA)

    def upsert_meeting(self, transcript: Transcript, minutes: MinutesDraft | None = None) -> None:
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO meetings(meeting_id, title, transcript_json, minutes_json, created_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(meeting_id) DO UPDATE SET
                  title=excluded.title,
                  transcript_json=excluded.transcript_json,
                  minutes_json=excluded.minutes_json
                """,
                (
                    transcript.meeting_id,
                    transcript.title,
                    json.dumps(to_dict(transcript), ensure_ascii=False),
                    json.dumps(to_dict(minutes), ensure_ascii=False) if minutes else None,
                    transcript.created_at,
                ),
            )

    def get_transcript(self, meeting_id: str) -> Transcript:
        with self._connect() as con:
            row = con.execute("SELECT transcript_json FROM meetings WHERE meeting_id = ?", (meeting_id,)).fetchone()
        if not row:
            raise KeyError(f"Meeting not found: {meeting_id}")
        return transcript_from_dict(json.loads(row[0]))

    def get_minutes(self, meeting_id: str) -> MinutesDraft | None:
        with self._connect() as con:
            row = con.execute("SELECT minutes_json FROM meetings WHERE meeting_id = ?", (meeting_id,)).fetchone()
        if not row:
            raise KeyError(f"Meeting not found: {meeting_id}")
        return minutes_from_dict(json.loads(row[0])) if row[0] else None

    def list_meetings(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute("SELECT meeting_id, title, created_at, minutes_json IS NOT NULL FROM meetings ORDER BY created_at DESC").fetchall()
        return [
            {"meeting_id": r[0], "title": r[1], "created_at": r[2], "has_minutes": bool(r[3])}
            for r in rows
        ]
