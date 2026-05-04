from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterable, List

from meeting_agent.core.schemas import TranscriptSegment
from meeting_agent.providers.asr.base import TranscriptDelta


@dataclass
class RollingTranscriptBuffer:
    """Stores recent final transcript segments for realtime UX.

    A production realtime system would combine this with VAD, partial-token updates,
    delayed correction, and incremental summarization.
    """

    max_segments: int = 50
    _segments: Deque[TranscriptSegment] = field(default_factory=deque)
    _counter: int = 0

    def ingest_delta(self, delta: TranscriptDelta) -> TranscriptSegment | None:
        if not delta.is_final:
            return None
        self._counter += 1
        segment = TranscriptSegment(
            id=f"live_{self._counter:04d}",
            text=delta.text,
            start_ms=delta.start_ms,
            end_ms=delta.end_ms,
            speaker_name=delta.speaker_name,
            confidence=delta.confidence,
            source_model=delta.metadata.get("source_model", "stream"),
            metadata=dict(delta.metadata),
        )
        self._segments.append(segment)
        while len(self._segments) > self.max_segments:
            self._segments.popleft()
        return segment

    def recent_segments(self) -> list[TranscriptSegment]:
        return list(self._segments)

    def recent_text(self) -> str:
        return "\n".join(f"{s.speaker_name}: {s.text}" for s in self._segments)
