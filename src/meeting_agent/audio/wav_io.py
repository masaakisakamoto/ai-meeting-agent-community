from __future__ import annotations

import json
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from meeting_agent.providers.audio.base import AudioChunk


@dataclass(frozen=True)
class WavInfo:
    path: str
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int
    frame_count: int
    duration_ms: int
    pcm_bytes: int
    format: str = "wav/pcm_s16le"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def write_wav_from_chunks(chunks: Iterable[AudioChunk], path: str | Path) -> WavInfo:
    """Write PCM s16le audio chunks into a standard WAV file.

    The Community repository keeps real OS recording optional, but the audio
    pipeline still needs a deterministic, testable artifact. This writer is the
    boundary between capture providers and ASR providers.
    """

    chunk_list = list(chunks)
    if not chunk_list:
        raise ValueError("Cannot write WAV: no audio chunks were provided")

    sample_rate_hz = chunk_list[0].sample_rate_hz
    channels = chunk_list[0].channels
    if channels < 1:
        raise ValueError("Cannot write WAV: channel count must be >= 1")
    if sample_rate_hz < 8_000:
        raise ValueError("Cannot write WAV: sample rate must be >= 8000 Hz")

    for chunk in chunk_list:
        if chunk.sample_rate_hz != sample_rate_hz:
            raise ValueError("Cannot write WAV: chunks have mixed sample rates")
        if chunk.channels != channels:
            raise ValueError("Cannot write WAV: chunks have mixed channel counts")
        if len(chunk.pcm_s16le) % (2 * channels) != 0:
            raise ValueError("Cannot write WAV: chunk byte length is not frame-aligned")

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate_hz)
        for chunk in chunk_list:
            wav.writeframes(chunk.pcm_s16le)

    return read_wav_info(out)


def read_wav_info(path: str | Path) -> WavInfo:
    wav_path = Path(path)
    with wave.open(str(wav_path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width_bytes = wav.getsampwidth()
        sample_rate_hz = wav.getframerate()
        frame_count = wav.getnframes()
    duration_ms = int(round(frame_count * 1000 / sample_rate_hz)) if sample_rate_hz else 0
    return WavInfo(
        path=str(wav_path),
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        sample_width_bytes=sample_width_bytes,
        frame_count=frame_count,
        duration_ms=duration_ms,
        pcm_bytes=frame_count * channels * sample_width_bytes,
    )


def chunk_timeline(chunks: Sequence[AudioChunk]) -> list[dict]:
    return [
        {
            "sequence": chunk.sequence,
            "start_ms": chunk.start_ms,
            "end_ms": chunk.end_ms,
            "duration_ms": chunk.duration_ms(),
            "rms": chunk.rms,
            "is_speech": chunk.is_speech,
            "pcm_bytes": len(chunk.pcm_s16le),
            "metadata": dict(chunk.metadata),
        }
        for chunk in chunks
    ]
