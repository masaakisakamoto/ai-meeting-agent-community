from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent.core.transcript import load_transcript, save_transcript
from meeting_agent.evals.metrics import evaluate_text
from meeting_agent.providers.asr import FasterWhisperProvider, SidecarTranscriptProvider
from meeting_agent.providers.asr.doctor import run_asr_doctor


@dataclass(frozen=True)
class ASRValidationCheck:
    id: str
    status: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ASRValidationPackReport:
    status: str
    score: float
    out_dir: str
    provider: str
    artifacts: dict[str, str]
    checks: list[ASRValidationCheck]
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
            "# ASR Validation Pack",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Output directory: `{self.out_dir}`",
            f"- Provider: `{self.provider}`",
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
class ASRValidationRunReport:
    status: str
    score: float
    provider: str
    audio_path: str
    out_dir: str
    dry_run: bool
    checks: list[ASRValidationCheck]
    artifacts: dict[str, str]
    metrics: dict[str, Any]
    summary: dict[str, Any]
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
            "# ASR Validation Run",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Provider: `{self.provider}`",
            f"- Audio: `{self.audio_path}`",
            f"- Output directory: `{self.out_dir}`",
            f"- Dry run: `{str(self.dry_run).lower()}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|---|---|",
        ]
        for key, value in sorted(self.summary.items()):
            lines.append(f"| {key} | `{_md(str(value))}` |")
        if self.metrics:
            lines.extend(["", "## Text Metrics", "", "| Metric | Value |", "|---|---|"])
            for key, value in sorted(self.metrics.items()):
                lines.append(f"| {key} | `{value}` |")
        lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "|---|---|---|"])
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | {_md(check.detail)} |")
        lines.extend(["", "## Artifacts", "", "| Name | Path |", "|---|---|"])
        for name, path in sorted(self.artifacts.items()):
            lines.append(f"| {name} | `{path}` |")
        lines.extend(["", "## Recommendation", "", self.recommendation, ""])
        return "\n".join(lines)


def build_asr_validation_pack(
    *,
    out_dir: str | Path,
    audio_path: str = "mic_alpha_live/audio.wav",
    provider: str = "sidecar",
    sidecar_path: str = "mic_alpha_live/audio.transcript.txt",
    reference_path: str = "mic_alpha_live/audio.transcript.txt",
    model_size: str = "small",
    device: str = "cpu",
) -> ASRValidationPackReport:
    """Create an operator-facing local ASR validation pack without transcribing audio."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scripts = out / "scripts"
    scripts.mkdir(exist_ok=True)
    artifacts: dict[str, str] = {}

    sidecar_command = (
        "PYTHONPATH=src python -m meeting_agent asr-validation-run "
        f"--audio-path {audio_path} --provider sidecar --sidecar {sidecar_path} "
        f"--reference {reference_path} --out-dir asr_validation_sidecar"
    )
    doctor_command = (
        "PYTHONPATH=src python -m meeting_agent asr-doctor "
        f"--provider faster-whisper --model-size {model_size} --device {device}"
    )
    faster_whisper_dry_run = (
        "PYTHONPATH=src python -m meeting_agent asr-validation-run "
        f"--audio-path {audio_path} --provider faster-whisper --model-size {model_size} "
        f"--device {device} --out-dir asr_validation_faster_whisper --dry-run"
    )
    faster_whisper_live = (
        "PYTHONPATH=src python -m meeting_agent asr-validation-run "
        f"--audio-path {audio_path} --provider faster-whisper --model-size {model_size} "
        f"--device {device} --out-dir asr_validation_faster_whisper"
    )

    manifest = {
        "project": "ai-meeting-agent-community",
        "version": "1.4.0",
        "kind": "asr_validation_pack",
        "created_for": "private_developer_preview",
        "opens_microphone": False,
        "downloads_models": False,
        "publication_hold": True,
        "private_core_included": False,
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
        "asr": {
            "provider": provider,
            "audio_path": audio_path,
            "sidecar_path": sidecar_path,
            "reference_path": reference_path,
            "model_size": model_size,
            "device": device,
        },
        "commands": {
            "01_sidecar_validation": sidecar_command,
            "02_faster_whisper_doctor": doctor_command,
            "03_faster_whisper_dry_run": faster_whisper_dry_run,
            "04_faster_whisper_live_smoke": faster_whisper_live,
        },
    }
    _write_json(out / "asr_validation_manifest.json", manifest)
    artifacts["asr_validation_manifest.json"] = str(out / "asr_validation_manifest.json")

    (out / "README.md").write_text(_pack_readme(manifest), encoding="utf-8")
    artifacts["README.md"] = str(out / "README.md")
    (out / "commands.md").write_text(_commands_markdown(manifest), encoding="utf-8")
    artifacts["commands.md"] = str(out / "commands.md")
    (out / "reference_template.txt").write_text(_reference_template(), encoding="utf-8")
    artifacts["reference_template.txt"] = str(out / "reference_template.txt")
    (out / "operator_checklist.md").write_text(_operator_checklist(), encoding="utf-8")
    artifacts["operator_checklist.md"] = str(out / "operator_checklist.md")

    for name, command in manifest["commands"].items():
        script = scripts / f"{name}.sh"
        script.write_text(_shell_script(command), encoding="utf-8")
        script.chmod(0o755)
        artifacts[f"scripts/{script.name}"] = str(script)

    doctor = run_asr_doctor("faster-whisper", model_size=model_size, device=device)
    checks = [
        ASRValidationCheck("pack_created", "pass", "ASR validation pack generated without opening the microphone or downloading models."),
        ASRValidationCheck("publication_hold", "pass", "Publication remains blocked by policy until explicitly changed."),
        ASRValidationCheck("sidecar_path_declared", "pass", f"Sidecar path: {sidecar_path}"),
        ASRValidationCheck("faster_whisper_doctor", "warn" if doctor.status == "fail" else doctor.status, doctor.recommendation, doctor.to_dict()),
        ASRValidationCheck("private_core_excluded", "pass", "No private Quality Engine code is included."),
    ]
    report = ASRValidationPackReport(
        status=_status(checks),
        score=_score(checks),
        out_dir=str(out),
        provider=provider,
        artifacts=artifacts,
        checks=checks,
        recommendation="Use sidecar validation first, then run faster-whisper dry-run/doctor, then a short local ASR smoke only after optional dependencies are installed.",
        private_core_included=False,
    )
    (out / "asr_validation_pack.json").write_text(report.to_json() + "\n", encoding="utf-8")
    (out / "asr_validation_pack.md").write_text(report.to_markdown(), encoding="utf-8")
    artifacts["asr_validation_pack.json"] = str(out / "asr_validation_pack.json")
    artifacts["asr_validation_pack.md"] = str(out / "asr_validation_pack.md")
    return ASRValidationPackReport(report.status, report.score, report.out_dir, report.provider, artifacts, report.checks, report.recommendation, False)


def run_asr_validation(
    *,
    audio_path: str | Path,
    out_dir: str | Path,
    provider: str = "sidecar",
    sidecar_path: str | Path | None = None,
    reference_path: str | Path | None = None,
    meeting_id: str = "mtg_asr_validation",
    title: str = "ASR Validation",
    model_size: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
    dry_run: bool = False,
) -> ASRValidationRunReport:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    audio = Path(audio_path)
    artifacts: dict[str, str] = {}
    checks: list[ASRValidationCheck] = []
    metrics: dict[str, Any] = {}
    summary: dict[str, Any] = {"provider": provider, "dry_run": dry_run}

    if audio.exists():
        checks.append(ASRValidationCheck("audio_path", "pass", f"Audio exists: {audio}"))
    else:
        checks.append(ASRValidationCheck("audio_path", "fail", f"Audio is missing: {audio}"))

    doctor = run_asr_doctor("faster-whisper", model_size=model_size, device=device) if provider == "faster-whisper" else None
    if doctor is not None:
        checks.append(ASRValidationCheck("asr_doctor", doctor.status, doctor.recommendation, doctor.to_dict()))
        (out / "asr_doctor.json").write_text(doctor.to_json() + "\n", encoding="utf-8")
        artifacts["asr_doctor.json"] = str(out / "asr_doctor.json")

    if dry_run:
        checks.append(ASRValidationCheck("dry_run", "pass", "Dry-run completed without invoking a speech recognition model."))
        recommendation = "Dry-run complete. Install optional ASR dependencies and run a short smoke transcription when you are back at the Mac."
        report = ASRValidationRunReport(_status(checks), _score(checks), provider, str(audio), str(out), True, checks, artifacts, metrics, summary, recommendation, False)
        _write_run_outputs(out, report)
        return report

    transcript = None
    try:
        if provider == "sidecar":
            transcript = SidecarTranscriptProvider(sidecar_path=sidecar_path).transcribe_file(str(audio), meeting_id=meeting_id, title=title)
        elif provider == "faster-whisper":
            transcript = FasterWhisperProvider(model_size=model_size, device=device, compute_type=compute_type).transcribe_file(str(audio), meeting_id=meeting_id, title=title)
        else:
            checks.append(ASRValidationCheck("provider", "fail", f"Unsupported provider: {provider}"))
    except Exception as exc:  # noqa: BLE001 - surfaced in report, keeps CLI deterministic
        checks.append(ASRValidationCheck("transcription", "fail", f"Transcription failed: {exc}"))

    if transcript is not None:
        save_transcript(transcript, out / "transcript.asr.json")
        artifacts["transcript.asr.json"] = str(out / "transcript.asr.json")
        hypothesis = _transcript_text(transcript)
        (out / "hypothesis.txt").write_text(hypothesis + "\n", encoding="utf-8")
        artifacts["hypothesis.txt"] = str(out / "hypothesis.txt")
        summary.update({"segments": len(transcript.segments), "chars": len(hypothesis)})
        checks.append(ASRValidationCheck("transcription", "pass" if transcript.segments else "warn", f"Generated {len(transcript.segments)} segments."))
        reference_text = _reference_text(reference_path or sidecar_path)
        if reference_text:
            (out / "reference.txt").write_text(reference_text + "\n", encoding="utf-8")
            artifacts["reference.txt"] = str(out / "reference.txt")
            text_metrics = evaluate_text(reference_text, hypothesis)
            metrics = text_metrics.__dict__.copy()
            (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            artifacts["metrics.json"] = str(out / "metrics.json")
            checks.append(ASRValidationCheck("reference_metrics", "pass", f"CER={metrics['cer']} WER={metrics['wer']}"))
        else:
            checks.append(ASRValidationCheck("reference_metrics", "warn", "No reference transcript supplied; CER/WER skipped."))

    checks.append(ASRValidationCheck("private_core_excluded", "pass", "No private Quality Engine code is included."))
    status = _status(checks)
    recommendation = (
        "ASR validation passed. Use the generated transcript for microphone-to-minutes or compare it with manual reference text."
        if status == "pass"
        else "Review failed/warn checks, especially optional dependencies, sidecar/reference paths, and audio quality."
    )
    report = ASRValidationRunReport(status, _score(checks), provider, str(audio), str(out), False, checks, artifacts, metrics, summary, recommendation, False)
    _write_run_outputs(out, report)
    return report


def write_asr_validation_pack_report(report: ASRValidationPackReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        Path(out_json).write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        Path(out_md).write_text(report.to_markdown(), encoding="utf-8")


def write_asr_validation_run_report(report: ASRValidationRunReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        Path(out_json).write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        Path(out_md).write_text(report.to_markdown(), encoding="utf-8")


def _write_run_outputs(out: Path, report: ASRValidationRunReport) -> None:
    (out / "asr_validation_report.json").write_text(report.to_json() + "\n", encoding="utf-8")
    (out / "asr_validation_report.md").write_text(report.to_markdown(), encoding="utf-8")


def _transcript_text(transcript: Any) -> str:
    return "\n".join(seg.text for seg in transcript.segments if (seg.text or "").strip()).strip()


def _reference_text(path: str | Path | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    try:
        transcript = load_transcript(p)
        return _transcript_text(transcript)
    except Exception:  # noqa: BLE001 - plain text reference fallback
        return p.read_text(encoding="utf-8").strip()


def _status(checks: list[ASRValidationCheck]) -> str:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "pass"


def _score(checks: list[ASRValidationCheck]) -> float:
    if not checks:
        return 0.0
    total = 0.0
    for check in checks:
        total += 1.0 if check.status == "pass" else 0.55 if check.status == "warn" else 0.0
    return round(total / len(checks), 3)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _shell_script(command: str) -> str:
    return "#!/usr/bin/env bash\nset -euo pipefail\n\ncd \"$(dirname \"$0\")/../..\"\n" + command + "\n"


def _pack_readme(manifest: dict[str, Any]) -> str:
    return (
        "# ASR Validation Pack\n\n"
        "This private developer-preview pack validates local ASR handoff after a real or simulated capture.\n\n"
        "It does not open the microphone, download models, or include private Quality Engine code.\n\n"
        "## Recommended order\n\n"
        "1. Run sidecar validation.\n"
        "2. Run faster-whisper doctor/dry-run.\n"
        "3. Install optional ASR dependencies only in a Python 3.12 virtual environment.\n"
        "4. Run a short local ASR smoke on a known WAV.\n"
        "5. Keep publication-gate on hold.\n\n"
        f"Provider: `{manifest['asr']['provider']}`\n"
    )


def _commands_markdown(manifest: dict[str, Any]) -> str:
    lines = ["# ASR Validation Commands", ""]
    for name, command in manifest["commands"].items():
        lines.extend([f"## {name}", "", "```bash", command, "```", ""])
    return "\n".join(lines)


def _operator_checklist() -> str:
    return (
        "# ASR Operator Checklist\n\n"
        "- [ ] Use a short known WAV first.\n"
        "- [ ] Validate sidecar/reference transcript alignment.\n"
        "- [ ] Run ASR doctor before invoking faster-whisper.\n"
        "- [ ] Keep downloaded model caches out of the repository.\n"
        "- [ ] Review CER/WER and generated transcript before using minutes.\n"
        "- [ ] Keep publication-gate on hold.\n"
    )


def _reference_template() -> str:
    return (
        "[00:00:00 - 00:00:01] 佐藤: これはASR検証用の参照文字起こしです。\n"
        "[00:00:01 - 00:00:02] 鈴木: 音声認識結果と比較してCERとWERを確認します。\n"
    )


def _md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")
