from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterable, Dict

from meeting_agent.core.schemas import Transcript


@dataclass
class TranscriptDelta:
    text: str
    start_ms: int = 0
    end_ms: int = 0
    speaker_name: str = "Unknown"
    is_final: bool = False
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ASRCapabilities:
    streaming: bool = False
    file_transcription: bool = True
    diarization: bool = False
    word_timestamps: bool = False
    languages: tuple[str, ...] = ("ja", "en")


class ASRProvider(ABC):
    id: str
    name: str
    capabilities: ASRCapabilities

    @abstractmethod
    async def transcribe_stream(self, audio_stream: AsyncIterable[bytes]) -> AsyncIterable[TranscriptDelta]:
        raise NotImplementedError

    @abstractmethod
    def transcribe_file(self, audio_path: str, *, meeting_id: str, title: str = "Untitled Meeting") -> Transcript:
        raise NotImplementedError
