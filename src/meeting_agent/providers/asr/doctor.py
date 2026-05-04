from __future__ import annotations

import importlib.util
import json
import platform
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ASRDoctorReport:
    provider: str
    status: str
    score: float
    checks: list[dict] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def run_asr_doctor(provider: str = "faster-whisper", *, model_size: str = "small", device: str = "cpu") -> ASRDoctorReport:
    checks: list[dict] = []
    if provider != "faster-whisper":
        return ASRDoctorReport(
            provider=provider,
            status="warn",
            score=0.5,
            checks=[{"name": "provider", "status": "warn", "message": "Only faster-whisper doctor is implemented in Community v0.6."}],
            recommendation="Use `--provider faster-whisper` or implement a provider-specific doctor plugin.",
        )

    fw_spec = importlib.util.find_spec("faster_whisper")
    checks.append(
        {
            "name": "faster_whisper_dependency",
            "status": "pass" if fw_spec else "fail",
            "message": "faster-whisper is installed." if fw_spec else "faster-whisper is not installed. Install with `pip install .[asr]`.",
        }
    )
    checks.append(
        {
            "name": "python_version",
            "status": "pass",
            "message": platform.python_version(),
            "metadata": {"implementation": platform.python_implementation()},
        }
    )
    checks.append(
        {
            "name": "requested_model",
            "status": "pass",
            "message": f"model_size={model_size}, device={device}",
            "metadata": {"model_size": model_size, "device": device},
        }
    )

    if device == "cuda":
        # Keep this lightweight. We avoid importing GPU-specific packages here.
        checks.append(
            {
                "name": "cuda_note",
                "status": "warn",
                "message": "CUDA execution depends on local CTranslate2/GPU setup; run a short transcription smoke test on the target machine.",
            }
        )

    status = "pass"
    if any(check["status"] == "fail" for check in checks):
        status = "fail"
    elif any(check["status"] == "warn" for check in checks):
        status = "warn"
    score = 1.0
    for check in checks:
        if check["status"] == "warn":
            score -= 0.15
        elif check["status"] == "fail":
            score -= 0.35
    recommendation = (
        "ASR environment looks ready for a local smoke transcription."
        if status == "pass"
        else "Install missing optional dependencies and run a short WAV transcription before using this in a real meeting."
    )
    return ASRDoctorReport(provider=provider, status=status, score=round(max(0.0, score), 3), checks=checks, recommendation=recommendation)
