from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator, Literal

from meeting_agent.core.schemas import Transcript, TranscriptSegment, to_dict

ReplayEventType = Literal["segment_start", "segment_delta", "segment_final", "meeting_end"]


@dataclass(frozen=True)
class TranscriptReplaySettings:
    """Deterministic replay settings for transcript UI demos.

    This is intentionally not tied to real-time sleeping. The caller receives a
    timeline of events with relative offsets and can decide whether to sleep,
    stream over WebSocket, or render immediately in tests.
    """

    chars_per_delta: int = 24
    min_delta_ms: int = 120
    max_segment_gap_ms: int = 1800
    speed: float = 1.0

    def normalized(self) -> "TranscriptReplaySettings":
        return TranscriptReplaySettings(
            chars_per_delta=max(1, int(self.chars_per_delta)),
            min_delta_ms=max(0, int(self.min_delta_ms)),
            max_segment_gap_ms=max(0, int(self.max_segment_gap_ms)),
            speed=max(0.01, float(self.speed)),
        )


@dataclass(frozen=True)
class TranscriptReplayEvent:
    type: ReplayEventType
    meeting_id: str
    offset_ms: int
    segment_id: str | None = None
    speaker_name: str | None = None
    text: str = ""
    delta: str = ""
    start_ms: int | None = None
    end_ms: int | None = None
    sequence: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))


def iter_transcript_replay_events(
    transcript: Transcript,
    settings: TranscriptReplaySettings | None = None,
) -> Iterator[TranscriptReplayEvent]:
    """Yield deterministic transcript replay events for UI/WebSocket demos.

    The offsets are relative to replay start, not wall-clock time. This makes the
    function stable enough for tests and suitable for generating a static demo.
    """

    config = (settings or TranscriptReplaySettings()).normalized()
    segments = sorted(transcript.segments, key=lambda s: (s.start_ms, s.end_ms, s.id))
    last_source_ms = segments[0].start_ms if segments else 0
    replay_offset = 0
    sequence = 0

    for segment in segments:
        gap = max(0, segment.start_ms - last_source_ms)
        gap = min(gap, config.max_segment_gap_ms)
        replay_offset += int(gap / config.speed)
        sequence += 1
        yield TranscriptReplayEvent(
            type="segment_start",
            meeting_id=transcript.meeting_id,
            offset_ms=replay_offset,
            segment_id=segment.id,
            speaker_name=segment.speaker_name,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            sequence=sequence,
        )

        for delta in _chunk_text(segment.text, config.chars_per_delta):
            replay_offset += int(config.min_delta_ms / config.speed)
            sequence += 1
            yield TranscriptReplayEvent(
                type="segment_delta",
                meeting_id=transcript.meeting_id,
                offset_ms=replay_offset,
                segment_id=segment.id,
                speaker_name=segment.speaker_name,
                delta=delta,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                sequence=sequence,
            )

        replay_offset += int(config.min_delta_ms / config.speed)
        sequence += 1
        yield TranscriptReplayEvent(
            type="segment_final",
            meeting_id=transcript.meeting_id,
            offset_ms=replay_offset,
            segment_id=segment.id,
            speaker_name=segment.speaker_name,
            text=segment.text,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            sequence=sequence,
        )
        last_source_ms = segment.end_ms

    sequence += 1
    yield TranscriptReplayEvent(
        type="meeting_end",
        meeting_id=transcript.meeting_id,
        offset_ms=replay_offset + int(config.min_delta_ms / config.speed),
        sequence=sequence,
    )


def transcript_replay_payload(
    transcript: Transcript,
    settings: TranscriptReplaySettings | None = None,
) -> dict:
    events = [event.to_dict() for event in iter_transcript_replay_events(transcript, settings)]
    return {
        "meeting": {
            "meeting_id": transcript.meeting_id,
            "title": transcript.title,
            "language": transcript.language,
            "created_at": transcript.created_at,
            "segment_count": len(transcript.segments),
        },
        "settings": asdict((settings or TranscriptReplaySettings()).normalized()),
        "events": events,
    }


def write_replay_ndjson(
    transcript: Transcript,
    path: str | Path,
    settings: TranscriptReplaySettings | None = None,
) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    events = list(iter_transcript_replay_events(transcript, settings))
    path.write_text("\n".join(event.to_json_line() for event in events) + "\n", encoding="utf-8")
    return len(events)


def write_replay_json(
    transcript: Transcript,
    path: str | Path,
    settings: TranscriptReplaySettings | None = None,
) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = transcript_replay_payload(transcript, settings)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(payload["events"])


def _chunk_text(text: str, size: int) -> Iterable[str]:
    text = text or ""
    for idx in range(0, len(text), size):
        yield text[idx : idx + size]
