from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from meeting_agent.providers.audio.base import AudioCaptureConfig, AudioCaptureProvider, AudioChunk, AudioDevice


@dataclass
class WavFileAudioProvider(AudioCaptureProvider):
    """Audio provider that replays an existing WAV file as AudioChunk objects."""

    wav_path: str | Path
    id: str = "wav-file"
    name: str = "WAV File Audio Provider"

    def list_devices(self) -> list[AudioDevice]:
        info = self._info()
        return [
            AudioDevice(
                id=f"file:{Path(self.wav_path)}",
                name=Path(self.wav_path).name,
                kind="file",
                channels=info["channels"],
                sample_rate_hz=info["sample_rate_hz"],
                is_default=True,
                metadata={"path": str(self.wav_path), "duration_ms": info["duration_ms"]},
            )
        ]

    def capture(self, config: AudioCaptureConfig, *, session_id: str) -> Iterable[AudioChunk]:
        wav_path = Path(self.wav_path)
        with wave.open(str(wav_path), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            if sample_width != 2:
                raise ValueError("Only PCM s16le WAV files are supported by WavFileAudioProvider")
            frames_per_chunk = max(1, int(sample_rate * max(20, config.chunk_ms) / 1000))
            sequence = 0
            start_frame = 0
            while True:
                pcm = wav.readframes(frames_per_chunk)
                if not pcm:
                    break
                frame_count = len(pcm) // (sample_width * channels)
                end_frame = start_frame + frame_count
                sequence += 1
                yield AudioChunk(
                    session_id=session_id,
                    sequence=sequence,
                    start_ms=int(start_frame * 1000 / sample_rate),
                    end_ms=int(end_frame * 1000 / sample_rate),
                    sample_rate_hz=sample_rate,
                    channels=channels,
                    pcm_s16le=pcm,
                    rms=0.0,
                    is_speech=True,
                    metadata={"provider": self.id, "path": str(wav_path)},
                )
                start_frame = end_frame

    def _info(self) -> dict:
        with wave.open(str(self.wav_path), "rb") as wav:
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()
            frames = wav.getnframes()
        return {
            "channels": channels,
            "sample_rate_hz": sample_rate,
            "duration_ms": int(round(frames * 1000 / sample_rate)) if sample_rate else 0,
        }
