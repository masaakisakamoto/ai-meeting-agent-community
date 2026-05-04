from __future__ import annotations

import json
import math
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

_PCM16_MAX = 32768.0


@dataclass(frozen=True)
class AudioQualityThresholds:
    """Deterministic thresholds for OSS-safe audio diagnostics.

    The thresholds are intentionally conservative. They are not a replacement for
    a production acoustic model, but they catch common recording problems early:
    silence, very low gain, clipping, and unsupported WAV formats.
    """

    min_duration_ms: int = 1000
    min_rms_dbfs: float = -45.0
    max_rms_dbfs: float = -6.0
    max_clipping_ratio: float = 0.01
    max_silence_ratio: float = 0.75
    silence_threshold_dbfs: float = -50.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AudioQualityReport:
    path: str
    status: str
    score: float
    duration_ms: int
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int
    frame_count: int
    rms_linear: float
    peak_linear: float
    rms_dbfs: float
    peak_dbfs: float
    silence_ratio: float
    clipping_ratio: float
    warnings: list[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def analyze_wav_quality(
    path: str | Path,
    *,
    thresholds: AudioQualityThresholds | None = None,
    chunk_frames: int = 4096,
) -> AudioQualityReport:
    """Analyze a PCM WAV file and return a deterministic quality report."""

    thresholds = thresholds or AudioQualityThresholds()
    wav_path = Path(path)
    warnings: list[str] = []
    checks: dict[str, dict] = {}

    with wave.open(str(wav_path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width_bytes = wav.getsampwidth()
        sample_rate_hz = wav.getframerate()
        frame_count = wav.getnframes()
        if sample_width_bytes != 2:
            warnings.append("Only PCM s16le WAV is fully supported by the Community quality analyzer.")
        total_samples = frame_count * channels
        sum_sq = 0.0
        peak_abs = 0
        clipping_count = 0
        silence_count = 0
        silence_abs = int(round(_PCM16_MAX * _dbfs_to_linear(thresholds.silence_threshold_dbfs)))
        samples_read = 0

        while True:
            raw = wav.readframes(max(1, chunk_frames))
            if not raw:
                break
            samples = _iter_pcm_s16le(raw)
            for sample in samples:
                abs_sample = abs(sample)
                peak_abs = max(peak_abs, abs_sample)
                sum_sq += float(sample) * float(sample)
                if abs_sample >= 32760:
                    clipping_count += 1
                if abs_sample <= silence_abs:
                    silence_count += 1
                samples_read += 1

    duration_ms = int(round(frame_count * 1000 / sample_rate_hz)) if sample_rate_hz else 0
    if samples_read == 0:
        rms_linear = 0.0
        peak_linear = 0.0
        clipping_ratio = 0.0
        silence_ratio = 1.0
    else:
        rms_linear = min(1.0, math.sqrt(sum_sq / samples_read) / _PCM16_MAX)
        peak_linear = min(1.0, peak_abs / _PCM16_MAX)
        clipping_ratio = clipping_count / samples_read
        silence_ratio = silence_count / samples_read
    rms_dbfs = _linear_to_dbfs(rms_linear)
    peak_dbfs = _linear_to_dbfs(peak_linear)

    checks["duration"] = {
        "status": "pass" if duration_ms >= thresholds.min_duration_ms else "warn",
        "value_ms": duration_ms,
        "minimum_ms": thresholds.min_duration_ms,
    }
    checks["rms_level"] = {
        "status": "pass" if thresholds.min_rms_dbfs <= rms_dbfs <= thresholds.max_rms_dbfs else "warn",
        "value_dbfs": rms_dbfs,
        "minimum_dbfs": thresholds.min_rms_dbfs,
        "maximum_dbfs": thresholds.max_rms_dbfs,
    }
    checks["clipping"] = {
        "status": "pass" if clipping_ratio <= thresholds.max_clipping_ratio else "fail",
        "value": clipping_ratio,
        "maximum": thresholds.max_clipping_ratio,
    }
    checks["silence"] = {
        "status": "pass" if silence_ratio <= thresholds.max_silence_ratio else "warn",
        "value": silence_ratio,
        "maximum": thresholds.max_silence_ratio,
    }
    checks["format"] = {
        "status": "pass" if sample_width_bytes == 2 and channels >= 1 and sample_rate_hz >= 8000 else "fail",
        "sample_width_bytes": sample_width_bytes,
        "channels": channels,
        "sample_rate_hz": sample_rate_hz,
    }

    if checks["duration"]["status"] != "pass":
        warnings.append("Audio is very short; transcription and diagnostics may be unreliable.")
    if checks["rms_level"]["status"] != "pass":
        if rms_dbfs < thresholds.min_rms_dbfs:
            warnings.append("Audio level is low. Move the microphone closer or increase input gain.")
        elif rms_dbfs > thresholds.max_rms_dbfs:
            warnings.append("Audio level is very hot. Lower input gain to reduce distortion risk.")
    if checks["clipping"]["status"] != "pass":
        warnings.append("Audio appears clipped. Lower input gain or avoid overloaded virtual audio devices.")
    if checks["silence"]["status"] != "pass":
        warnings.append("Large portions are near silence. Verify the selected input device and meeting audio route.")
    if checks["format"]["status"] != "pass":
        warnings.append("WAV format is outside the recommended PCM s16le / >=8kHz range.")

    score = _score(checks)
    status = "pass"
    if any(item["status"] == "fail" for item in checks.values()):
        status = "fail"
    elif any(item["status"] == "warn" for item in checks.values()):
        status = "warn"

    return AudioQualityReport(
        path=str(wav_path),
        status=status,
        score=score,
        duration_ms=duration_ms,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        sample_width_bytes=sample_width_bytes,
        frame_count=frame_count,
        rms_linear=round(rms_linear, 6),
        peak_linear=round(peak_linear, 6),
        rms_dbfs=round(rms_dbfs, 2),
        peak_dbfs=round(peak_dbfs, 2),
        silence_ratio=round(silence_ratio, 6),
        clipping_ratio=round(clipping_ratio, 6),
        warnings=warnings,
        checks=checks,
    )


def _iter_pcm_s16le(raw: bytes) -> Iterable[int]:
    # Avoid struct.iter_unpack overhead in tight loops and keep Python 3.10 compatibility.
    for idx in range(0, len(raw) - 1, 2):
        value = int.from_bytes(raw[idx : idx + 2], byteorder="little", signed=True)
        yield value


def _linear_to_dbfs(value: float) -> float:
    if value <= 0.0:
        return -120.0
    return 20.0 * math.log10(value)


def _dbfs_to_linear(value: float) -> float:
    return 10 ** (value / 20.0)


def _score(checks: dict[str, dict]) -> float:
    score = 1.0
    for item in checks.values():
        if item["status"] == "warn":
            score -= 0.15
        elif item["status"] == "fail":
            score -= 0.35
    return round(max(0.0, score), 3)
