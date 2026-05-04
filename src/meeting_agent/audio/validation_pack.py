from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent.audio.live_guard import LIVE_CONFIRMATION_PHRASE, evaluate_recording_safety_gate
from meeting_agent.audio.quality import analyze_wav_quality
from meeting_agent.audio.wav_io import read_wav_info
from meeting_agent.workflows.microphone_minutes import evaluate_post_capture_gate


@dataclass(frozen=True)
class CaptureValidationCheck:
    id: str
    status: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CaptureValidationPackReport:
    status: str
    score: float
    out_dir: str
    duration_ms: int
    device_id: str
    artifacts: dict[str, str]
    checks: list[CaptureValidationCheck]
    recommendation: str
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Real Capture Validation Pack",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Output directory: `{self.out_dir}`",
            f"- Duration: `{self.duration_ms} ms`",
            f"- Device ID: `{self.device_id}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "|---|---|---|",
        ]
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | {_md(check.detail)} |")
        lines.extend(["", "## Artifacts", "", "| Name | Path |", "|---|---|"])
        for name, path in sorted(self.artifacts.items()):
            lines.append(f"| {name} | `{path}` |")
        lines.extend(["", "## Recommendation", "", self.recommendation, ""])
        return "\n".join(lines)


@dataclass(frozen=True)
class CaptureValidationRunReport:
    status: str
    score: float
    mic_dir: str
    minutes_dir: str | None
    checks: list[CaptureValidationCheck]
    artifacts: dict[str, str]
    recommendation: str
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Real Capture Validation Run",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Microphone directory: `{self.mic_dir}`",
            f"- Minutes directory: `{self.minutes_dir or 'not provided'}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "|---|---|---|",
        ]
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | {_md(check.detail)} |")
        lines.extend(["", "## Artifacts", "", "| Name | Path |", "|---|---|"])
        for name, path in sorted(self.artifacts.items()):
            lines.append(f"| {name} | `{path}` |")
        lines.extend(["", "## Recommendation", "", self.recommendation, ""])
        return "\n".join(lines)


def build_capture_validation_pack(
    *,
    out_dir: str | Path,
    duration_ms: int = 3_000,
    device_id: str = "microphone:default",
    sample_rate_hz: int = 16_000,
    channels: int = 1,
    chunk_ms: int = 250,
    mic_dir: str = "mic_alpha_live",
    minutes_dir: str = "mic_minutes_live",
) -> CaptureValidationPackReport:
    """Create an operator-facing validation pack without opening the microphone."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scripts = out / "scripts"
    scripts.mkdir(exist_ok=True)
    checks: list[CaptureValidationCheck] = []
    artifacts: dict[str, str] = {}

    dry_run_command = (
        "PYTHONPATH=src python -m meeting_agent record-microphone-alpha "
        f"--out-dir {mic_dir} --duration-ms {duration_ms} --device-id {device_id}"
    )
    live_command = (
        "PYTHONPATH=src python -m meeting_agent record-microphone-alpha "
        f"--out-dir {mic_dir} --duration-ms {duration_ms} --device-id {device_id} "
        "--live --confirm-live-recording --notice-acknowledged --participants-notified"
    )
    post_command = (
        "PYTHONPATH=src python -m meeting_agent microphone-to-minutes "
        f"--mic-dir {mic_dir} --out-dir {minutes_dir} --provider sidecar"
    )
    validate_command = (
        "PYTHONPATH=src python -m meeting_agent capture-validation-run "
        f"--mic-dir {mic_dir} --minutes-dir {minutes_dir} "
        "--out-json capture_validation_run.json --out-md capture_validation_run.md"
    )

    manifest = {
        "project": "ai-meeting-agent-community",
        "version": "1.4.0",
        "kind": "real_capture_validation_pack",
        "created_for": "private_developer_preview",
        "opens_microphone": False,
        "publication_hold": True,
        "private_core_included": False,
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
        "capture": {
            "device_id": device_id,
            "duration_ms": duration_ms,
            "sample_rate_hz": sample_rate_hz,
            "channels": channels,
            "chunk_ms": chunk_ms,
            "confirmation_phrase": LIVE_CONFIRMATION_PHRASE,
        },
        "directories": {"mic_dir": mic_dir, "minutes_dir": minutes_dir},
        "commands": {
            "01_dry_run": dry_run_command,
            "02_live_capture": live_command,
            "03_post_capture_minutes": post_command,
            "04_validate_run": validate_command,
        },
    }
    _write_json(out / "capture_validation_manifest.json", manifest)
    artifacts["capture_validation_manifest.json"] = str(out / "capture_validation_manifest.json")

    readme = _pack_readme(manifest)
    (out / "README.md").write_text(readme, encoding="utf-8")
    artifacts["README.md"] = str(out / "README.md")

    commands_md = _commands_markdown(manifest)
    (out / "commands.md").write_text(commands_md, encoding="utf-8")
    artifacts["commands.md"] = str(out / "commands.md")

    (out / "sidecar_template.txt").write_text(_sidecar_template(), encoding="utf-8")
    artifacts["sidecar_template.txt"] = str(out / "sidecar_template.txt")

    (scripts / "01_dry_run.sh").write_text(_shell_script(dry_run_command), encoding="utf-8")
    (scripts / "02_live_capture.sh").write_text(_shell_script(live_command), encoding="utf-8")
    (scripts / "03_post_capture_minutes.sh").write_text(_shell_script(post_command), encoding="utf-8")
    (scripts / "04_validate_run.sh").write_text(_shell_script(validate_command), encoding="utf-8")
    for path in sorted(scripts.glob("*.sh")):
        path.chmod(0o755)
        artifacts[f"scripts/{path.name}"] = str(path)

    notice = (
        "# Operator Safety Checklist\n\n"
        "- [ ] Use a private test environment first.\n"
        "- [ ] Confirm the microphone input device.\n"
        "- [ ] Notify all participants before recording.\n"
        "- [ ] Use the live command only after dry-run and safety gate checks pass.\n"
        "- [ ] Keep publication-gate on hold.\n"
        "- [ ] Review generated minutes before sharing.\n"
    )
    (out / "operator_checklist.md").write_text(notice, encoding="utf-8")
    artifacts["operator_checklist.md"] = str(out / "operator_checklist.md")

    safety = evaluate_recording_safety_gate(live_requested=False, duration_ms=duration_ms, publication_hold=True)
    checks.append(CaptureValidationCheck("pack_created", "pass", "Validation pack was generated without opening the microphone."))
    checks.append(CaptureValidationCheck("dry_run_default", "pass", "Pack defaults to dry-run and explicit live confirmation is required."))
    checks.append(CaptureValidationCheck("publication_hold", "pass", "Publication remains blocked by policy until explicitly changed."))
    checks.append(CaptureValidationCheck("safety_gate_dry_run", safety.status, safety.recommendation, safety.to_dict()))
    checks.append(CaptureValidationCheck("private_core_excluded", "pass", "No private Quality Engine code is included."))
    report = CaptureValidationPackReport(
        status=_status(checks),
        score=_score(checks),
        out_dir=str(out),
        duration_ms=duration_ms,
        device_id=device_id,
        artifacts=artifacts,
        checks=checks,
        recommendation="Use this pack when you are back on the Mac: run dry-run, then live capture with explicit consent, then post-capture minutes, then validation.",
        private_core_included=False,
    )
    (out / "capture_validation_pack.json").write_text(report.to_json() + "\n", encoding="utf-8")
    (out / "capture_validation_pack.md").write_text(report.to_markdown(), encoding="utf-8")
    artifacts["capture_validation_pack.json"] = str(out / "capture_validation_pack.json")
    artifacts["capture_validation_pack.md"] = str(out / "capture_validation_pack.md")
    return CaptureValidationPackReport(report.status, report.score, report.out_dir, report.duration_ms, report.device_id, artifacts, report.checks, report.recommendation, False)


def evaluate_capture_validation_run(
    *,
    mic_dir: str | Path,
    minutes_dir: str | Path | None = None,
    provider: str = "sidecar",
) -> CaptureValidationRunReport:
    mic = Path(mic_dir)
    minutes = Path(minutes_dir) if minutes_dir else None
    checks: list[CaptureValidationCheck] = []
    artifacts: dict[str, str] = {}
    checks.append(CaptureValidationCheck("mic_dir", "pass" if mic.exists() else "fail", f"Microphone directory: {mic}"))

    safety_path = mic / "recording_safety_gate.json"
    checks.append(CaptureValidationCheck("recording_safety_gate", "pass" if safety_path.exists() else "warn", f"Safety gate artifact: {safety_path}"))
    if safety_path.exists():
        artifacts["recording_safety_gate.json"] = str(safety_path)
        try:
            safety = json.loads(safety_path.read_text(encoding="utf-8"))
            checks.append(CaptureValidationCheck("live_allowed_trace", "pass" if safety.get("live_allowed") in {True, False} else "warn", f"Safety gate status: {safety.get('status')} / live_allowed={safety.get('live_allowed')}", safety))
        except json.JSONDecodeError:
            checks.append(CaptureValidationCheck("recording_safety_gate_json", "fail", "Safety gate JSON is invalid."))

    audit_path = mic / "audit.jsonl"
    checks.append(CaptureValidationCheck("audit_log", "pass" if audit_path.exists() else "warn", f"Audit log: {audit_path}"))
    if audit_path.exists():
        artifacts["audit.jsonl"] = str(audit_path)
        events = [line for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        checks.append(CaptureValidationCheck("audit_events", "pass" if events else "warn", f"Audit event count: {len(events)}", {"events": len(events)}))

    alpha_path = mic / "microphone_alpha.json"
    checks.append(CaptureValidationCheck("microphone_alpha_report", "pass" if alpha_path.exists() else "warn", f"Microphone alpha report: {alpha_path}"))
    if alpha_path.exists():
        artifacts["microphone_alpha.json"] = str(alpha_path)

    audio = mic / "audio.wav"
    if audio.exists():
        artifacts["audio.wav"] = str(audio)
        try:
            info = read_wav_info(audio)
            quality = analyze_wav_quality(audio)
            checks.append(CaptureValidationCheck("audio_wav", "pass", f"{info.duration_ms} ms / {info.sample_rate_hz} Hz / {info.channels} channel(s)", info.to_dict()))
            checks.append(CaptureValidationCheck("audio_quality", quality.status, f"Quality score {quality.score}; RMS {quality.rms_dbfs} dBFS", quality.to_dict()))
        except Exception as exc:
            checks.append(CaptureValidationCheck("audio_inspection", "fail", f"Could not inspect audio.wav: {exc}"))
    else:
        checks.append(CaptureValidationCheck("audio_wav", "fail", "audio.wav is missing; run live microphone capture first."))

    gate = evaluate_post_capture_gate(mic, provider=provider)
    checks.append(CaptureValidationCheck("post_capture_gate", gate.status, gate.recommendation, gate.to_dict()))

    if minutes:
        checks.append(CaptureValidationCheck("minutes_dir", "pass" if minutes.exists() else "warn", f"Minutes directory: {minutes}"))
        expected = ["minutes.html", "minutes.md", "meeting_from_microphone.json", "microphone_minutes_report.json"]
        for name in expected:
            path = minutes / name
            checks.append(CaptureValidationCheck(f"minutes_{name}", "pass" if path.exists() else "warn", f"{name}: {path}"))
            if path.exists():
                artifacts[f"minutes/{name}"] = str(path)
    else:
        checks.append(CaptureValidationCheck("minutes_dir", "warn", "No minutes directory supplied; run microphone-to-minutes after live capture."))

    checks.append(CaptureValidationCheck("private_core_excluded", "pass", "Validation uses Community-only components."))
    status = _status(checks)
    recommendation = "Capture validation passed or is ready for final post-capture review." if status in {"pass", "warn"} else "Resolve failed checks before trusting the live-capture output."
    return CaptureValidationRunReport(status, _score(checks), str(mic), str(minutes) if minutes else None, checks, artifacts, recommendation, False)


def write_capture_validation_pack_report(report: CaptureValidationPackReport, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def write_capture_validation_run_report(report: CaptureValidationRunReport, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def _pack_readme(manifest: dict[str, Any]) -> str:
    commands = manifest["commands"]
    return f"""# Real Capture Validation Pack

This pack is for **private developer preview** validation only. It does not open the microphone by itself.

## Safety

- Publication remains on hold.
- Private core is not included.
- Live capture requires explicit confirmation and participant notification.
- Confirmation phrase: `{LIVE_CONFIRMATION_PHRASE}`

## Order

1. Run dry-run.
2. Run live capture only in a safe test environment.
3. Copy or edit `audio.transcript.txt` if using sidecar ASR.
4. Generate microphone minutes.
5. Validate the full capture run.

## Commands

```bash
{commands['01_dry_run']}

{commands['02_live_capture']}

cp capture_validation_pack/sidecar_template.txt {manifest['directories']['mic_dir']}/audio.transcript.txt

{commands['03_post_capture_minutes']}

{commands['04_validate_run']}
```
"""


def _commands_markdown(manifest: dict[str, Any]) -> str:
    lines = ["# Real Capture Commands", ""]
    for name, command in manifest["commands"].items():
        lines.extend([f"## {name}", "", "```bash", command, "```", ""])
    return "\n".join(lines)


def _sidecar_template() -> str:
    return "\n".join([
        "[00:00:00 - 00:00:01] 自分: これは実マイク録音の検証です。v1.4では録音後の議事録化まで確認します。",
        "[00:00:01 - 00:00:02] 自分: 次のアクションは音声品質と証跡付き議事録を確認することです。",
        "[00:00:02 - 00:00:03] 自分: 公開ゲートはholdのまま維持します。",
        "",
    ])


def _shell_script(command: str) -> str:
    return "#!/usr/bin/env bash\nset -euo pipefail\ncd \"$(dirname \"$0\")/../..\"\n" + command + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _status(checks: list[CaptureValidationCheck]) -> str:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "pass"


def _score(checks: list[CaptureValidationCheck]) -> float:
    score = 1.0
    for check in checks:
        if check.status == "warn":
            score -= 0.06
        elif check.status == "fail":
            score -= 0.22
    return round(max(0.0, score), 3)


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
