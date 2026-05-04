from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable, Protocol


@dataclass(frozen=True)
class AudioDevice:
    id: str
    name: str
    kind: str  # microphone, system, virtual, file, simulated
    channels: int = 1
    sample_rate_hz: int = 16_000
    is_default: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AudioCaptureConfig:
    device_id: str
    sample_rate_hz: int = 16_000
    channels: int = 1
    chunk_ms: int = 250
    language_hint: str = "ja"
    enable_vad: bool = True
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AudioChunk:
    session_id: str
    sequence: int
    start_ms: int
    end_ms: int
    sample_rate_hz: int
    channels: int
    pcm_s16le: bytes = b""
    rms: float = 0.0
    is_speech: bool = True
    metadata: dict = field(default_factory=dict)

    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    def to_public_dict(self) -> dict:
        data = asdict(self)
        data["pcm_s16le"] = f"<{len(self.pcm_s16le)} bytes>"
        return data


class AudioCaptureProvider(Protocol):
    id: str
    name: str

    def list_devices(self) -> list[AudioDevice]:
        ...

    def capture(self, config: AudioCaptureConfig, *, session_id: str) -> Iterable[AudioChunk]:
        ...
