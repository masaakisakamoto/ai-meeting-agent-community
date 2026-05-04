from __future__ import annotations

import importlib.util
import json
import platform
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent.audio.levels import analyze_audio_levels, write_audio_level_report
from meeting_agent.audio.live_guard import LIVE_CONFIRMATION_PHRASE, evaluate_recording_safety_gate, write_recording_safety_gate_report
from meeting_agent.audio.preflight import assess_capture_readiness
from meeting_agent.audio.quality import analyze_wav_quality
from meeting_agent.audio.session import capture_session_to_wav
from meeting_agent.compliance.audit import AuditLogger
from meeting_agent.compliance.consent import render_recording_notice
from meeting_agent.providers.audio import AudioCaptureConfig, SoundDeviceMicrophoneProvider


@dataclass(frozen=True)
class MicrophoneAlphaCheck:
    id: str
    status: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MicrophoneAlphaReport:
    status: str
    score: float
    mode: str
    python_version: str
    platform: str
    provider_id: str
    selected_device_id: str
    duration_ms: int
    checks: list[MicrophoneAlphaCheck]
    devices: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    recommendation: str = ""
    safety_gate: dict[str, Any] = field(default_factory=dict)
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Real Microphone Alpha Report",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Mode: `{self.mode}`",
            f"- Python: `{self.python_version}`",
            f"- Platform: `{self.platform}`",
            f"- Provider: `{self.provider_id}`",
            f"- Selected device: `{self.selected_device_id}`",
            f"- Duration: `{self.duration_ms} ms`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "|---|---|---|",
        ]
        for check in self.checks:
            detail = str(check.detail).replace("|", "\\|")
            lines.append(f"| {check.id} | `{check.status}` | {detail} |")
        lines.extend(["", "## Devices", ""])
        if self.devices:
            lines.extend(["| ID | Name | Channels | Sample rate | Default |", "|---|---|---:|---:|---|"])
            for device in self.devices[:40]:
                lines.append(
                    f"| `{device.get('id','')}` | {_md(device.get('name',''))} | {device.get('channels','')} | {device.get('sample_rate_hz','')} | {device.get('is_default', False)} |"
                )
        else:
            lines.append("No real input devices are available in this environment, or optional audio dependencies are not installed.")
        lines.extend(["", "## Artifacts", ""])
        if self.artifacts:
            for name, path in sorted(self.artifacts.items()):
                lines.append(f"- `{name}`: `{path}`")
        else:
            lines.append("No recording artifacts were created in dry-run mode.")
        lines.extend(["", "## Recording Safety Gate", ""])
        if self.safety_gate:
            lines.append(f"- Status: `{self.safety_gate.get('status', 'unknown')}`")
            lines.append(f"- Live allowed: `{str(self.safety_gate.get('live_allowed', False)).lower()}`")
            lines.append(f"- Confirmation phrase: `{self.safety_gate.get('confirmation_phrase', LIVE_CONFIRMATION_PHRASE)}`")
        else:
            lines.append("No safety gate data attached.")
        lines.extend(["", "## Recommendation", "", self.recommendation, ""])
        return "\n".join(lines)


def run_microphone_alpha_doctor(
    *,
    device_id: str = "microphone:default",
    sample_rate_hz: int = 16_000,
    channels: int = 1,
    chunk_ms: int = 250,
    duration_ms: int = 3_000,
    require_sounddevice: bool = False,
) -> MicrophoneAlphaReport:
    provider = SoundDeviceMicrophoneProvider()
    checks: list[MicrophoneAlphaCheck] = []
    py = sys.version_info
    py_ok = (3, 10) <= (py.major, py.minor) <= (3, 12)
    checks.append(
        MicrophoneAlphaCheck(
            "python_version",
            "pass" if py_ok else "warn",
            "Python 3.10-3.12 is recommended for optional audio dependencies." if not py_ok else "Python is in the recommended range.",
            {"major": py.major, "minor": py.minor, "micro": py.micro},
        )
    )
    sounddevice_installed = importlib.util.find_spec("sounddevice") is not None
    numpy_installed = importlib.util.find_spec("numpy") is not None
    checks.append(
        MicrophoneAlphaCheck(
            "sounddevice_dependency",
            "pass" if sounddevice_installed else ("fail" if require_sounddevice else "warn"),
            "sounddevice is installed." if sounddevice_installed else "sounddevice is not installed. Use Python 3.12 venv and `pip install -e .[audio]`.",
        )
    )
    checks.append(
        MicrophoneAlphaCheck(
            "numpy_dependency",
            "pass" if numpy_installed else ("fail" if require_sounddevice else "warn"),
            "numpy is installed." if numpy_installed else "numpy is not installed. It is required for real microphone capture.",
        )
    )
    devices: list[dict[str, Any]] = []
    if sounddevice_installed:
        try:
            devices = [device.to_dict() for device in provider.list_devices()]
            checks.append(
                MicrophoneAlphaCheck(
                    "input_devices",
                    "pass" if devices else "warn",
                    f"Detected {len(devices)} input device(s)." if devices else "No input device was detected.",
                    {"count": len(devices)},
                )
            )
        except Exception as exc:  # pragma: no cover - machine dependent
            checks.append(MicrophoneAlphaCheck("input_devices", "fail" if require_sounddevice else "warn", f"Could not list input devices: {exc}"))
    else:
        checks.append(MicrophoneAlphaCheck("input_devices", "warn", "Skipped real device listing because sounddevice is not installed."))

    if sounddevice_installed:
        try:
            readiness = assess_capture_readiness(
                provider,
                AudioCaptureConfig(device_id=device_id, sample_rate_hz=sample_rate_hz, channels=channels, chunk_ms=chunk_ms, metadata={"duration_ms": duration_ms}),
                require_real_device=True,
            )
            checks.append(MicrophoneAlphaCheck("capture_readiness", readiness.status, readiness.recommendation, readiness.to_dict()))
        except Exception as exc:  # pragma: no cover - machine dependent
            checks.append(MicrophoneAlphaCheck("capture_readiness", "warn", f"Readiness check could not complete: {exc}"))
    else:
        checks.append(MicrophoneAlphaCheck("capture_readiness", "warn", "Install optional audio dependencies before real capture readiness checks."))

    if platform.system() == "Darwin":
        checks.append(MicrophoneAlphaCheck("macos_permission_hint", "warn", "The first real recording may require Terminal/Python microphone permission in System Settings."))
    else:
        checks.append(MicrophoneAlphaCheck("os_permission_hint", "pass", "Review OS-level microphone permissions before live capture."))

    status = _status(checks)
    score = _score(checks)
    recommendation = _doctor_recommendation(status, sounddevice_installed)
    return MicrophoneAlphaReport(
        status=status,
        score=score,
        mode="dry_run",
        python_version=platform.python_version(),
        platform=platform.platform(),
        provider_id=provider.id,
        selected_device_id=device_id,
        duration_ms=duration_ms,
        checks=checks,
        devices=devices,
        recommendation=recommendation,
        private_core_included=False,
    )


def run_microphone_alpha_recording(
    *,
    out_dir: str | Path,
    session_id: str = "mic_alpha",
    device_id: str = "microphone:default",
    duration_ms: int = 3_000,
    sample_rate_hz: int = 16_000,
    channels: int = 1,
    chunk_ms: int = 250,
    window_ms: int = 100,
    dry_run: bool = True,
    confirm_live_recording: str | bool | None = None,
    notice_acknowledged: bool = False,
    participants_notified: bool = False,
    actor_id: str = "local_developer",
) -> MicrophoneAlphaReport:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    safety_gate = evaluate_recording_safety_gate(
        live_requested=not dry_run,
        confirmation=confirm_live_recording,
        notice_acknowledged=notice_acknowledged,
        participants_notified=participants_notified,
        duration_ms=duration_ms,
        publication_hold=True,
    )
    write_recording_safety_gate_report(safety_gate, out_json=out / "recording_safety_gate.json", out_md=out / "recording_safety_gate.md")
    notice_path = out / "recording_notice.md"
    notice_path.write_text(render_recording_notice(), encoding="utf-8")
    audit = AuditLogger(out / "audit.jsonl")
    audit.record(
        "microphone_alpha_requested",
        actor_id=actor_id,
        target_id=session_id,
        metadata={"dry_run": dry_run, "duration_ms": duration_ms, "safety_gate_status": safety_gate.status, "live_allowed": safety_gate.live_allowed},
    )
    base_artifacts = {
        "recording_safety_gate.json": str(out / "recording_safety_gate.json"),
        "recording_safety_gate.md": str(out / "recording_safety_gate.md"),
        "recording_notice.md": str(notice_path),
        "audit.jsonl": str(out / "audit.jsonl"),
    }
    if dry_run:
        report = run_microphone_alpha_doctor(device_id=device_id, sample_rate_hz=sample_rate_hz, channels=channels, chunk_ms=chunk_ms, duration_ms=duration_ms)
        report = MicrophoneAlphaReport(
            status=report.status,
            score=report.score,
            mode=report.mode,
            python_version=report.python_version,
            platform=report.platform,
            provider_id=report.provider_id,
            selected_device_id=report.selected_device_id,
            duration_ms=report.duration_ms,
            checks=report.checks,
            devices=report.devices,
            artifacts=base_artifacts,
            recommendation=report.recommendation,
            safety_gate=safety_gate.to_dict(),
            private_core_included=False,
        )
        write_microphone_alpha_report(report, out_json=out / "microphone_alpha.json", out_md=out / "microphone_alpha.md")
        return report

    if not safety_gate.live_allowed:
        checks = [MicrophoneAlphaCheck(f"safety_{check.id}", check.status, check.detail, check.metadata) for check in safety_gate.checks]
        report = MicrophoneAlphaReport(
            "fail",
            safety_gate.score,
            "blocked_live_capture",
            platform.python_version(),
            platform.platform(),
            "sounddevice-microphone",
            device_id,
            duration_ms,
            checks,
            [],
            base_artifacts,
            safety_gate.recommendation,
            safety_gate.to_dict(),
            False,
        )
        audit.record("microphone_alpha_blocked", actor_id=actor_id, target_id=session_id, metadata={"reason": "safety_gate", "safety_gate": safety_gate.to_dict()})
        write_microphone_alpha_report(report, out_json=out / "microphone_alpha.json", out_md=out / "microphone_alpha.md")
        return report

    provider = SoundDeviceMicrophoneProvider()
    config = AudioCaptureConfig(device_id=device_id, sample_rate_hz=sample_rate_hz, channels=channels, chunk_ms=chunk_ms, metadata={"duration_ms": duration_ms})
    checks: list[MicrophoneAlphaCheck] = []
    devices: list[dict[str, Any]] = []
    artifacts: dict[str, str] = dict(base_artifacts)
    doctor = run_microphone_alpha_doctor(device_id=device_id, sample_rate_hz=sample_rate_hz, channels=channels, chunk_ms=chunk_ms, duration_ms=duration_ms, require_sounddevice=True)
    checks.extend(doctor.checks)
    devices = doctor.devices
    if doctor.status == "fail":
        report = MicrophoneAlphaReport("fail", doctor.score, "real_capture", platform.python_version(), platform.platform(), provider.id, device_id, duration_ms, checks, devices, artifacts, "Resolve failed microphone doctor checks before live capture.", safety_gate.to_dict(), False)
        write_microphone_alpha_report(report, out_json=out / "microphone_alpha.json", out_md=out / "microphone_alpha.md")
        return report
    try:
        audit.record("microphone_live_capture_started", actor_id=actor_id, target_id=session_id, metadata={"duration_ms": duration_ms, "device_id": device_id})
        manifest = capture_session_to_wav(provider, config, session_id=session_id, wav_path=out / "audio.wav", manifest_path=out / "audio_session.json")
        artifacts["audio.wav"] = str(out / "audio.wav")
        artifacts["audio_session.json"] = str(out / "audio_session.json")
        checks.append(MicrophoneAlphaCheck("wav_recording", "pass" if manifest.chunk_count else "fail", f"Captured {manifest.chunk_count} chunk(s), duration {manifest.duration_ms} ms."))
        quality = analyze_wav_quality(out / "audio.wav")
        (out / "audio_quality.json").write_text(quality.to_json() + "\n", encoding="utf-8")
        artifacts["audio_quality.json"] = str(out / "audio_quality.json")
        checks.append(MicrophoneAlphaCheck("audio_quality", quality.status, f"Quality score {quality.score}; RMS {quality.rms_dbfs} dBFS."))
        levels = analyze_audio_levels(out / "audio.wav", window_ms=window_ms)
        write_audio_level_report(levels, out / "audio_levels.json", out / "audio_levels.md")
        artifacts["audio_levels.json"] = str(out / "audio_levels.json")
        artifacts["audio_levels.md"] = str(out / "audio_levels.md")
        checks.append(MicrophoneAlphaCheck("audio_levels", "pass", f"Generated {levels.frame_count} level-meter frame(s)."))
        audit.record("microphone_live_capture_completed", actor_id=actor_id, target_id=session_id, metadata={"status": "captured", "chunk_count": manifest.chunk_count, "duration_ms": manifest.duration_ms})
    except Exception as exc:  # pragma: no cover - machine dependent
        checks.append(MicrophoneAlphaCheck("wav_recording", "fail", f"Real microphone capture failed: {exc}"))
        audit.record("microphone_live_capture_failed", actor_id=actor_id, target_id=session_id, metadata={"error": str(exc)})
    status = _status(checks)
    recommendation = "Real microphone alpha capture completed. Inspect audio_quality.json before ASR." if status in {"pass", "warn"} else "Grant microphone permission, choose a valid input device, and retry."
    report = MicrophoneAlphaReport(status, _score(checks), "real_capture", platform.python_version(), platform.platform(), provider.id, device_id, duration_ms, checks, devices, artifacts, recommendation, safety_gate.to_dict(), False)
    write_microphone_alpha_report(report, out_json=out / "microphone_alpha.json", out_md=out / "microphone_alpha.md")
    return report


def write_microphone_alpha_report(report: MicrophoneAlphaReport, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def microphone_setup_guide() -> str:
    return """# Real Microphone Alpha Setup

Keep this repository private while validating real microphone capture.

## Recommended macOS environment

```bash
cd /path/to/ai-meeting-agent-community
python3.12 -m venv "$HOME/.venvs/ai-meeting-agent-312"
source "$HOME/.venvs/ai-meeting-agent-312/bin/activate"
python -m pip install --upgrade pip
python -m pip install -e '.[audio]'
```

## Safe checks

```bash
PYTHONPATH=src python -m meeting_agent microphone-doctor --out-json mic_doctor.json --out-md mic_doctor.md
PYTHONPATH=src python -m meeting_agent list-audio-devices --provider microphone
```

## First short recording

```bash
PYTHONPATH=src python -m meeting_agent record-microphone-alpha --out-dir mic_alpha_out --duration-ms 3000 --live \
  --confirm-live-recording --notice-acknowledged --participants-notified
open mic_alpha_out/microphone_alpha.md
```

On macOS, grant microphone permission to Terminal, iTerm, VS Code, or Python if prompted.
"""


def write_microphone_setup_guide(path: str | Path) -> None:
    Path(path).write_text(microphone_setup_guide(), encoding="utf-8")


def _status(checks: list[MicrophoneAlphaCheck]) -> str:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "pass"


def _score(checks: list[MicrophoneAlphaCheck]) -> float:
    score = 1.0
    for check in checks:
        if check.status == "warn":
            score -= 0.1
        elif check.status == "fail":
            score -= 0.3
    return round(max(0.0, score), 3)


def _doctor_recommendation(status: str, sounddevice_installed: bool) -> str:
    if status == "pass":
        return "Microphone alpha environment is ready. Run a short controlled recording and inspect audio diagnostics."
    if not sounddevice_installed:
        return "Create a Python 3.12 virtual environment and install optional audio dependencies: `pip install -e '.[audio]'`."
    if status == "warn":
        return "Review warnings, especially macOS microphone permission and input device selection, before recording."
    return "Resolve failed checks before starting real microphone capture."


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
