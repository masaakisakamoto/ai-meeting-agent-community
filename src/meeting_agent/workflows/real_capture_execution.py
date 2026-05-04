from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent.audio import analyze_wav_quality, read_wav_info
from meeting_agent.audio.live_guard import LIVE_CONFIRMATION_PHRASE
from meeting_agent.core.schemas import utc_now_iso


@dataclass(frozen=True)
class RealCaptureCheck:
    id: str
    status: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RealCaptureExecutionPackReport:
    status: str
    score: float
    out_dir: str
    generated_at: str
    commands: dict[str, str]
    artifacts: dict[str, str]
    checks: list[RealCaptureCheck]
    recommendation: str
    opens_microphone: bool = False
    publication_hold: bool = True
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Real Microphone Validation Execution Pack",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Output directory: `{self.out_dir}`",
            f"- Opens microphone: `{str(self.opens_microphone).lower()}`",
            f"- Publication hold: `{str(self.publication_hold).lower()}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            f"- Generated at: `{self.generated_at}`",
            "",
            "## Commands",
            "",
        ]
        for name, command in self.commands.items():
            lines.extend([f"### {name}", "", "```bash", command, "```", ""])
        lines.extend(["## Checks", "", "| Check | Status | Detail |", "|---|---|---|"])
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | {_md(check.detail)} |")
        lines.extend(["", "## Artifacts", "", "| Name | Path |", "|---|---|"])
        for name, path in sorted(self.artifacts.items()):
            lines.append(f"| {name} | `{path}` |")
        lines.extend(["", "## Recommendation", "", self.recommendation, ""])
        return "\n".join(lines)


@dataclass(frozen=True)
class RealCaptureExecutionGateReport:
    status: str
    score: float
    generated_at: str
    mic_dir: str
    minutes_dir: str | None
    asr_minutes_dir: str | None
    checks: list[RealCaptureCheck]
    summary: dict[str, Any]
    recommendation: str
    publication_hold: bool = True
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Real Capture Execution Gate",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Microphone directory: `{self.mic_dir}`",
            f"- Minutes directory: `{self.minutes_dir or 'not provided'}`",
            f"- ASR minutes directory: `{self.asr_minutes_dir or 'not provided'}`",
            f"- Publication hold: `{str(self.publication_hold).lower()}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            f"- Generated at: `{self.generated_at}`",
            "",
            "## Summary",
            "",
            "| Key | Value |",
            "|---|---|",
        ]
        for key, value in sorted(self.summary.items()):
            lines.append(f"| {key} | `{_md(str(value))}` |")
        lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "|---|---|---|"])
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | {_md(check.detail)} |")
        lines.extend(["", "## Recommendation", "", self.recommendation, ""])
        return "\n".join(lines)


def build_real_capture_execution_pack(
    *,
    out_dir: str | Path,
    duration_ms: int = 3000,
    device_id: str = "microphone:default",
    sample_rate_hz: int = 16000,
    channels: int = 1,
    chunk_ms: int = 250,
    mic_dir: str = "mic_alpha_live",
    minutes_dir: str = "mic_minutes_live",
    asr_minutes_dir: str = "asr_minutes_live",
    provider: str = "sidecar",
) -> RealCaptureExecutionPackReport:
    """Create a private live-capture execution pack without opening the microphone.

    The pack is meant for the maintainer's Mac. It contains scripts and
    checklists for running a short live capture, post-capture minutes, ASR
    validation, and the real-capture execution gate. It never imports the
    private Quality Engine and it never opens a microphone by itself.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scripts = out / "scripts"
    scripts.mkdir(exist_ok=True)

    commands = {
        "01_environment_doctor": (
            "PYTHONPATH=src python -m meeting_agent dev-env-doctor --root . --out-json dev_environment.json --out-md dev_environment.md\n"
            "PYTHONPATH=src python -m meeting_agent microphone-doctor --out-json mic_doctor.json --out-md mic_doctor.md"
        ),
        "02_live_capture": (
            "PYTHONPATH=src python -m meeting_agent record-microphone-alpha "
            f"--out-dir {mic_dir} --duration-ms {duration_ms} --device-id {device_id} "
            f"--sample-rate {sample_rate_hz} --channels {channels} --chunk-ms {chunk_ms} "
            "--live --confirm-live-recording --notice-acknowledged --participants-notified"
        ),
        "03_post_capture_minutes": (
            "test -f {mic_dir}/audio.transcript.txt || cp {pack}/sidecar_template.txt {mic_dir}/audio.transcript.txt\n"
            "PYTHONPATH=src python -m meeting_agent microphone-to-minutes "
            f"--mic-dir {mic_dir} --out-dir {minutes_dir} --provider {provider}"
        ).format(mic_dir=mic_dir, pack=str(out)),
        "04_asr_to_minutes": (
            "PYTHONPATH=src python -m meeting_agent asr-to-minutes "
            f"--audio-path {mic_dir}/audio.wav --provider {provider} "
            f"--sidecar {mic_dir}/audio.transcript.txt --reference {mic_dir}/audio.transcript.txt "
            f"--out-dir {asr_minutes_dir}"
        ),
        "05_execution_gate": (
            "PYTHONPATH=src python -m meeting_agent real-capture-execution-gate "
            f"--mic-dir {mic_dir} --minutes-dir {minutes_dir} --asr-minutes-dir {asr_minutes_dir} "
            "--out-json real_capture_execution_gate.json --out-md real_capture_execution_gate.md"
        ),
    }

    script_paths: dict[str, str] = {}
    for name, command in commands.items():
        script_path = scripts / f"{name}.sh"
        script_path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n\n" + command + "\n", encoding="utf-8")
        try:
            script_path.chmod(0o755)
        except OSError:
            pass
        script_paths[f"script_{name}"] = str(script_path)

    sidecar_template = out / "sidecar_template.txt"
    sidecar_template.write_text(
        "[00:00:00 - 00:00:01] 話者1: これは実マイク検証用の参照文字起こしです。\n"
        "[00:00:01 - 00:00:02] 話者1: 音声が聞き取れることを確認します。\n"
        "[00:00:02 - 00:00:03] 話者1: 録音後に議事録生成とASR検証を実行します。\n",
        encoding="utf-8",
    )

    manifest = {
        "project": "ai-meeting-agent-community",
        "version": "1.6.0",
        "kind": "real_capture_execution_pack",
        "created_for": "private_developer_preview",
        "opens_microphone": False,
        "publication_hold": True,
        "private_core_included": False,
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
        "capture": {
            "duration_ms": duration_ms,
            "device_id": device_id,
            "sample_rate_hz": sample_rate_hz,
            "channels": channels,
            "chunk_ms": chunk_ms,
            "confirmation_phrase": LIVE_CONFIRMATION_PHRASE,
        },
        "directories": {"mic_dir": mic_dir, "minutes_dir": minutes_dir, "asr_minutes_dir": asr_minutes_dir},
        "provider": provider,
        "commands": commands,
    }

    readme = out / "README.md"
    readme.write_text(
        "# Real Microphone Validation Execution Pack\n\n"
        "This private pack guides the maintainer through one short real microphone validation run. "
        "It does not open the microphone by itself.\n\n"
        "## Order\n\n"
        "1. Run environment doctor.\n"
        "2. Run one explicit live capture with recording notice and participant notification.\n"
        "3. Add or edit `audio.transcript.txt` for sidecar validation.\n"
        "4. Generate microphone minutes.\n"
        "5. Run ASR to minutes.\n"
        "6. Run the execution gate.\n\n"
        "Keep publication-gate on hold until all public-alpha exit criteria are met.\n",
        encoding="utf-8",
    )
    checklist = out / "operator_checklist.md"
    checklist.write_text(
        "# Operator Checklist\n\n"
        "- [ ] Repository is private.\n"
        "- [ ] Participants are notified before any real recording.\n"
        "- [ ] The recording notice is acknowledged.\n"
        "- [ ] Live capture duration is intentionally short.\n"
        "- [ ] `audit.jsonl`, `recording_safety_gate.json`, and `audio.wav` are inspected.\n"
        "- [ ] Public announcement remains blocked.\n",
        encoding="utf-8",
    )
    commands_md = out / "commands.md"
    commands_md.write_text(
        "# Real Capture Commands\n\n" + "\n".join(
            f"## {name}\n\n```bash\n{command}\n```\n" for name, command in commands.items()
        ),
        encoding="utf-8",
    )
    manifest_path = out / "real_capture_execution_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    artifacts = {
        "README.md": str(readme),
        "commands.md": str(commands_md),
        "operator_checklist.md": str(checklist),
        "sidecar_template.txt": str(sidecar_template),
        "real_capture_execution_manifest.json": str(manifest_path),
    }
    artifacts.update(script_paths)
    checks = [
        RealCaptureCheck("opens_microphone", "pass", "Pack generation does not open the microphone."),
        RealCaptureCheck("live_confirmation_command", "pass", "Live command includes explicit recording confirmation flags."),
        RealCaptureCheck("recording_notice", "pass", "Live command requires notice acknowledgement and participant notification."),
        RealCaptureCheck("publication_hold", "pass", "Publication remains blocked while real capture is validated privately."),
        RealCaptureCheck("private_core_excluded", "pass", "Private Quality Engine is not included."),
    ]
    report = RealCaptureExecutionPackReport(
        status=_status(checks),
        score=_score(checks),
        out_dir=str(out),
        generated_at=utc_now_iso(),
        commands=commands,
        artifacts=artifacts,
        checks=checks,
        recommendation="Use this pack on the Mac to perform one short live capture, then run the execution gate. Keep publication hold enabled.",
    )
    write_real_capture_execution_pack_report(report, out_json=out / "real_capture_execution_pack.json", out_md=out / "real_capture_execution_pack.md")
    return report


def evaluate_real_capture_execution(
    *,
    mic_dir: str | Path,
    minutes_dir: str | Path | None = None,
    asr_minutes_dir: str | Path | None = None,
    require_live_artifacts: bool = True,
) -> RealCaptureExecutionGateReport:
    mic = Path(mic_dir)
    minutes = Path(minutes_dir) if minutes_dir else None
    asr_minutes = Path(asr_minutes_dir) if asr_minutes_dir else None
    checks: list[RealCaptureCheck] = []
    summary: dict[str, Any] = {
        "live_capture_detected": False,
        "audio_duration_ms": None,
        "audio_quality_status": None,
        "microphone_mode": None,
        "audit_has_live_started": False,
        "audit_has_live_completed": False,
    }

    checks.append(RealCaptureCheck("mic_dir", "pass" if mic.exists() else "warn", "Microphone directory exists." if mic.exists() else "Microphone directory is missing."))
    mic_report = _read_json(mic / "microphone_alpha.json")
    if mic_report:
        mode = str(mic_report.get("mode", "unknown"))
        summary["microphone_mode"] = mode
        is_live = mode == "real_capture"
        summary["live_capture_detected"] = is_live
        checks.append(RealCaptureCheck("microphone_alpha_report", "pass" if is_live else ("warn" if require_live_artifacts else "pass"), f"microphone_alpha.json mode={mode}.", {"mode": mode}))
    else:
        checks.append(RealCaptureCheck("microphone_alpha_report", "warn", "microphone_alpha.json is missing."))

    safety = _read_json(mic / "recording_safety_gate.json")
    if safety:
        live_ok = bool(safety.get("live_requested")) and bool(safety.get("live_allowed"))
        checks.append(RealCaptureCheck("recording_safety_gate", "pass" if live_ok else ("warn" if require_live_artifacts else "pass"), f"live_requested={safety.get('live_requested')} live_allowed={safety.get('live_allowed')}.", {"status": safety.get("status")}))
    else:
        checks.append(RealCaptureCheck("recording_safety_gate", "warn", "recording_safety_gate.json is missing."))

    audit_path = mic / "audit.jsonl"
    if audit_path.exists():
        events = _read_audit_events(audit_path)
        has_started = "microphone_live_capture_started" in events
        has_completed = "microphone_live_capture_completed" in events
        summary["audit_has_live_started"] = has_started
        summary["audit_has_live_completed"] = has_completed
        status = "pass" if has_started and has_completed else ("warn" if require_live_artifacts else "pass")
        checks.append(RealCaptureCheck("audit_live_sequence", status, f"audit events include started={has_started}, completed={has_completed}.", {"events": events}))
    else:
        checks.append(RealCaptureCheck("audit_live_sequence", "warn", "audit.jsonl is missing."))

    audio = mic / "audio.wav"
    if audio.exists():
        checks.append(RealCaptureCheck("audio_wav", "pass", f"audio.wav found: {audio}"))
        try:
            info = read_wav_info(audio)
            summary["audio_duration_ms"] = info.duration_ms
            checks.append(RealCaptureCheck("audio_info", "pass", f"{info.duration_ms} ms / {info.sample_rate_hz} Hz / {info.channels} channel(s).", info.to_dict()))
            quality = analyze_wav_quality(audio)
            summary["audio_quality_status"] = quality.status
            checks.append(RealCaptureCheck("audio_quality", quality.status, f"Quality score {quality.score}; RMS {quality.rms_dbfs} dBFS.", quality.to_dict()))
        except Exception as exc:
            checks.append(RealCaptureCheck("audio_readable", "fail", f"Could not inspect audio.wav: {exc}"))
    else:
        checks.append(RealCaptureCheck("audio_wav", "warn" if require_live_artifacts else "pass", "audio.wav is missing."))

    session = _read_json(mic / "audio_session.json")
    if session:
        provider_id = str(session.get("provider_id", "unknown"))
        status = "pass" if provider_id != "simulated-audio" else ("warn" if require_live_artifacts else "pass")
        checks.append(RealCaptureCheck("audio_session_provider", status, f"audio_session provider_id={provider_id}.", {"provider_id": provider_id}))
    else:
        checks.append(RealCaptureCheck("audio_session_provider", "warn", "audio_session.json is missing."))

    if minutes:
        minutes_html = minutes / "minutes.html"
        minutes_report = minutes / "microphone_minutes_report.json"
        checks.append(RealCaptureCheck("microphone_minutes_html", "pass" if minutes_html.exists() else "warn", "microphone minutes HTML exists." if minutes_html.exists() else "microphone minutes HTML is missing."))
        checks.append(RealCaptureCheck("microphone_minutes_report", "pass" if minutes_report.exists() else "warn", "microphone minutes report exists." if minutes_report.exists() else "microphone minutes report is missing."))
    else:
        checks.append(RealCaptureCheck("microphone_minutes_dir", "warn", "minutes_dir was not provided."))

    if asr_minutes:
        asr_report = asr_minutes / "asr_minutes_report.json"
        asr_html = asr_minutes / "minutes.html"
        checks.append(RealCaptureCheck("asr_minutes_report", "pass" if asr_report.exists() else "warn", "ASR minutes report exists." if asr_report.exists() else "ASR minutes report is missing."))
        checks.append(RealCaptureCheck("asr_minutes_html", "pass" if asr_html.exists() else "warn", "ASR minutes HTML exists." if asr_html.exists() else "ASR minutes HTML is missing."))
    else:
        checks.append(RealCaptureCheck("asr_minutes_dir", "warn", "asr_minutes_dir was not provided."))

    checks.append(RealCaptureCheck("publication_hold", "pass", "Publication remains blocked during private real-capture execution."))
    checks.append(RealCaptureCheck("private_core_excluded", "pass", "Private Quality Engine is not included."))

    status = _status(checks)
    recommendation = _gate_recommendation(status, checks, require_live_artifacts)
    return RealCaptureExecutionGateReport(
        status=status,
        score=_score(checks),
        generated_at=utc_now_iso(),
        mic_dir=str(mic),
        minutes_dir=str(minutes) if minutes else None,
        asr_minutes_dir=str(asr_minutes) if asr_minutes else None,
        checks=checks,
        summary=summary,
        recommendation=recommendation,
        publication_hold=True,
        private_core_included=False,
    )


def write_real_capture_execution_pack_report(report: RealCaptureExecutionPackReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def write_real_capture_execution_gate_report(report: RealCaptureExecutionGateReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_audit_events(path: Path) -> list[str]:
    events: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            event = payload.get("event_type") or payload.get("event") or payload.get("type")
            if event:
                events.append(str(event))
        except json.JSONDecodeError:
            continue
    return events


def _status(checks: list[RealCaptureCheck]) -> str:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "pass"


def _score(checks: list[RealCaptureCheck]) -> float:
    score = 1.0
    for check in checks:
        if check.status == "warn":
            score -= 0.06
        elif check.status == "fail":
            score -= 0.22
    return round(max(0.0, score), 3)


def _gate_recommendation(status: str, checks: list[RealCaptureCheck], require_live_artifacts: bool) -> str:
    if status == "pass":
        return "Real microphone execution evidence is complete enough for the next private alpha gate. Keep publication hold until local ASR and launch assets are also complete."
    missing = [check.id for check in checks if check.status != "pass"]
    if require_live_artifacts:
        return "Keep this private. Complete the missing live-capture evidence before public-alpha readiness: " + ", ".join(missing[:8])
    return "Gate completed in non-live mode. Use this report for dry-run troubleshooting only; live capture evidence is still required before public announcement."


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
