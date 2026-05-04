from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from meeting_agent.providers.audio.base import AudioCaptureConfig, AudioCaptureProvider, AudioChunk, AudioDevice


@dataclass
class SoundDeviceMicrophoneProvider(AudioCaptureProvider):
    """Optional real microphone provider backed by the `sounddevice` package.

    The dependency is intentionally optional so the Community repository remains
    lightweight and CI-safe. Install with `pip install .[audio]` before using
    `record-microphone` or listing real input devices.
    """

    id: str = "sounddevice-microphone"
    name: str = "SoundDevice Microphone Capture"

    def list_devices(self) -> list[AudioDevice]:
        sd = _load_sounddevice()
        devices = sd.query_devices()
        default_input = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else None
        out: list[AudioDevice] = []
        for index, info in enumerate(devices):
            max_input_channels = int(info.get("max_input_channels", 0))
            if max_input_channels <= 0:
                continue
            out.append(
                AudioDevice(
                    id=f"sounddevice:{index}",
                    name=str(info.get("name", f"Input {index}")),
                    kind="microphone",
                    channels=max(1, min(2, max_input_channels)),
                    sample_rate_hz=int(info.get("default_samplerate", 16000)),
                    is_default=index == default_input,
                    metadata={"sounddevice_index": index, "max_input_channels": max_input_channels},
                )
            )
        if not out:
            out.append(
                AudioDevice(
                    id="microphone:default",
                    name="Default Microphone",
                    kind="microphone",
                    channels=1,
                    sample_rate_hz=16000,
                    is_default=True,
                    metadata={"warning": "sounddevice returned no explicit input devices"},
                )
            )
        return out

    def capture(self, config: AudioCaptureConfig, *, session_id: str) -> Iterable[AudioChunk]:
        sd = _load_sounddevice()
        np = _load_numpy()
        sample_rate = max(8000, int(config.sample_rate_hz))
        channels = max(1, int(config.channels))
        chunk_ms = max(20, int(config.chunk_ms))
        duration_ms = int(config.metadata.get("duration_ms", 3000))
        total_frames = int(sample_rate * max(1, duration_ms) / 1000)
        frames_per_chunk = max(1, int(sample_rate * chunk_ms / 1000))
        device = _parse_sounddevice_id(config.device_id)
        frames_read = 0
        sequence = 0
        with sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
            device=device,
            blocksize=frames_per_chunk,
        ) as stream:
            while frames_read < total_frames:
                requested = min(frames_per_chunk, total_frames - frames_read)
                data, overflowed = stream.read(requested)
                pcm = _float32_to_pcm_s16le(data, np)
                rms = float(np.sqrt(np.mean(np.square(data)))) if data.size else 0.0
                start_frame = frames_read
                frames_read += requested
                sequence += 1
                yield AudioChunk(
                    session_id=session_id,
                    sequence=sequence,
                    start_ms=int(start_frame * 1000 / sample_rate),
                    end_ms=int(frames_read * 1000 / sample_rate),
                    sample_rate_hz=sample_rate,
                    channels=channels,
                    pcm_s16le=pcm,
                    rms=round(rms, 6),
                    is_speech=rms > 0.005,
                    metadata={
                        "provider": self.id,
                        "device": config.device_id,
                        "overflowed": bool(overflowed),
                    },
                )


def _load_sounddevice():
    try:
        import sounddevice as sd  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional package
        raise RuntimeError("sounddevice is not installed. Install optional audio support with `pip install .[audio]`.") from exc
    return sd


def _load_numpy():
    try:
        import numpy as np  # type: ignore
    except ImportError as exc:  # pragma: no cover - sounddevice normally brings numpy
        raise RuntimeError("numpy is required for microphone capture. Install optional audio support with `pip install .[audio]`.") from exc
    return np


def _parse_sounddevice_id(device_id: str):
    if device_id in {"", "default", "microphone:default"}:
        return None
    if device_id.startswith("sounddevice:"):
        value = device_id.split(":", 1)[1]
        try:
            return int(value)
        except ValueError:
            return value
    return device_id


def _float32_to_pcm_s16le(data, np) -> bytes:
    clipped = np.clip(data, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    return pcm.tobytes()
