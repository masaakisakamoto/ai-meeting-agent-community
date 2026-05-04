from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterable

from meeting_agent.providers.audio.base import AudioCaptureConfig, AudioCaptureProvider, AudioChunk, AudioDevice


@dataclass
class SimulatedAudioCaptureProvider(AudioCaptureProvider):
    """Dependency-free audio capture provider for demos and tests.

    It intentionally does not try to access a real microphone. Real OS audio
    capture belongs in optional providers so the Community repository remains
    safe to run on clean CI and easy to publish as OSS.
    """

    id: str = "simulated-audio"
    name: str = "Simulated Audio Capture"
    total_ms: int = 10_000
    tone_hz: float = 440.0

    def list_devices(self) -> list[AudioDevice]:
        return [
            AudioDevice(
                id="simulated:microphone",
                name="Simulated Microphone",
                kind="simulated",
                channels=1,
                sample_rate_hz=16_000,
                is_default=True,
                metadata={"safe_for_ci": True},
            )
        ]

    def capture(self, config: AudioCaptureConfig, *, session_id: str) -> Iterable[AudioChunk]:
        chunk_ms = max(20, config.chunk_ms)
        sample_rate = max(8_000, config.sample_rate_hz)
        channels = max(1, config.channels)
        sequence = 0
        for start_ms in range(0, max(0, self.total_ms), chunk_ms):
            end_ms = min(start_ms + chunk_ms, self.total_ms)
            sequence += 1
            pcm = _tone_pcm_s16le(
                duration_ms=end_ms - start_ms,
                sample_rate_hz=sample_rate,
                frequency_hz=self.tone_hz,
                channels=channels,
                phase_offset_ms=start_ms,
            )
            yield AudioChunk(
                session_id=session_id,
                sequence=sequence,
                start_ms=start_ms,
                end_ms=end_ms,
                sample_rate_hz=sample_rate,
                channels=channels,
                pcm_s16le=pcm,
                rms=0.18,
                is_speech=True,
                metadata={"provider": self.id, "simulated": True},
            )


def _tone_pcm_s16le(
    *,
    duration_ms: int,
    sample_rate_hz: int,
    frequency_hz: float,
    channels: int,
    phase_offset_ms: int = 0,
) -> bytes:
    total_samples = int(sample_rate_hz * max(0, duration_ms) / 1000)
    # v0.7 keeps simulated capture deterministic and CI-safe. A constant,
    # non-clipping PCM tone surrogate is enough for WAV persistence, audio
    # diagnostics, level-meter, and ASR workflow smoke tests; it avoids slow
    # per-sample Python sine loops during full test discovery.
    amplitude = 2500
    frame = struct.pack("<h", amplitude) * max(1, channels)
    return frame * total_samples
