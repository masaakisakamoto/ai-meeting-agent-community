from __future__ import annotations

import importlib.util
import json
from dataclasses import asdict, dataclass, field
from typing import Protocol

from meeting_agent.providers.audio.base import AudioCaptureConfig, AudioCaptureProvider, AudioDevice


@dataclass(frozen=True)
class CaptureReadinessCheck:
    name: str
    status: str
    message: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CaptureReadinessReport:
    provider_id: str
    status: str
    score: float
    devices: list[dict]
    selected_device_id: str
    checks: list[CaptureReadinessCheck]
    recommendation: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def assess_capture_readiness(
    provider: AudioCaptureProvider,
    config: AudioCaptureConfig,
    *,
    require_real_device: bool = False,
) -> CaptureReadinessReport:
    """Run provider-neutral checks before a recording session.

    This is intentionally deterministic and lightweight. It does not open the
    microphone unless the caller explicitly records. That keeps CI, public OSS
    previews, and user machines safe from surprise permission prompts.
    """

    checks: list[CaptureReadinessCheck] = []
    try:
        devices = provider.list_devices()
        checks.append(
            CaptureReadinessCheck(
                "list_devices",
                "pass",
                f"Provider returned {len(devices)} device(s).",
                {"count": len(devices)},
            )
        )
    except Exception as exc:  # pragma: no cover - defensive provider boundary
        devices = []
        checks.append(CaptureReadinessCheck("list_devices", "fail", f"Cannot list devices: {exc}"))

    selected = _select_device(devices, config.device_id)
    if selected:
        checks.append(
            CaptureReadinessCheck(
                "selected_device",
                "pass",
                f"Selected device is available: {selected.name}.",
                selected.to_dict(),
            )
        )
    else:
        checks.append(
            CaptureReadinessCheck(
                "selected_device",
                "fail" if require_real_device else "warn",
                "Selected device was not found. The provider may still support a runtime default device.",
                {"requested_device_id": config.device_id},
            )
        )

    checks.append(
        CaptureReadinessCheck(
            "sample_rate",
            "pass" if 8_000 <= config.sample_rate_hz <= 48_000 else "warn",
            "Sample rate is in the recommended range." if 8_000 <= config.sample_rate_hz <= 48_000 else "Unusual sample rate.",
            {"sample_rate_hz": config.sample_rate_hz},
        )
    )
    checks.append(
        CaptureReadinessCheck(
            "channels",
            "pass" if config.channels in {1, 2} else "warn",
            "Channel count is recommended." if config.channels in {1, 2} else "Unusual channel count.",
            {"channels": config.channels},
        )
    )
    checks.append(
        CaptureReadinessCheck(
            "chunk_ms",
            "pass" if 20 <= config.chunk_ms <= 2000 else "warn",
            "Chunk duration is suitable for realtime pipelines." if 20 <= config.chunk_ms <= 2000 else "Chunk duration may hurt latency or stability.",
            {"chunk_ms": config.chunk_ms},
        )
    )

    if provider.id in {"sounddevice-microphone", "microphone"}:
        installed = importlib.util.find_spec("sounddevice") is not None
        checks.append(
            CaptureReadinessCheck(
                "sounddevice_dependency",
                "pass" if installed else "fail",
                "sounddevice is installed." if installed else "sounddevice is not installed. Install with `pip install .[audio]`.",
                {"package": "sounddevice"},
            )
        )
    elif require_real_device:
        checks.append(
            CaptureReadinessCheck(
                "real_device_required",
                "warn",
                "The selected provider is not a real microphone provider.",
                {"provider_id": provider.id},
            )
        )

    score = _readiness_score(checks)
    status = "pass"
    if any(check.status == "fail" for check in checks):
        status = "fail"
    elif any(check.status == "warn" for check in checks):
        status = "warn"

    recommendation = _recommendation(status, provider.id, checks)
    return CaptureReadinessReport(
        provider_id=provider.id,
        status=status,
        score=score,
        devices=[device.to_dict() for device in devices],
        selected_device_id=config.device_id,
        checks=checks,
        recommendation=recommendation,
    )


def _select_device(devices: list[AudioDevice], device_id: str) -> AudioDevice | None:
    if device_id in {"default", "microphone:default", "simulated:microphone"}:
        for device in devices:
            if device.is_default:
                return device
    for device in devices:
        if device.id == device_id:
            return device
    return None


def _readiness_score(checks: list[CaptureReadinessCheck]) -> float:
    score = 1.0
    for check in checks:
        if check.status == "warn":
            score -= 0.1
        elif check.status == "fail":
            score -= 0.25
    return round(max(0.0, score), 3)


def _recommendation(status: str, provider_id: str, checks: list[CaptureReadinessCheck]) -> str:
    if status == "pass":
        return "Capture pipeline is ready for a controlled recording workflow."
    if provider_id in {"sounddevice-microphone", "microphone"} and any(c.name == "sounddevice_dependency" and c.status == "fail" for c in checks):
        return "Install optional audio dependencies and retry: `pip install .[audio]`."
    if any(c.name == "selected_device" and c.status in {"warn", "fail"} for c in checks):
        return "List devices, choose an available input device, then run a short test recording."
    return "Review warnings before starting a production recording session."
