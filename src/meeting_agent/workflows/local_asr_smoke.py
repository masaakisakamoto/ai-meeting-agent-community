from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent.core.schemas import utc_now_iso
from meeting_agent.providers.asr.doctor import run_asr_doctor
from meeting_agent.workflows.asr_minutes import run_asr_to_minutes_workflow
from meeting_agent.workflows.asr_validation import run_asr_validation


@dataclass(frozen=True)
class LocalASRSmokeCheck:
    id: str
    status: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LocalASRSmokePackReport:
    status: str
    score: float
    out_dir: str
    generated_at: str
    commands: dict[str, str]
    artifacts: dict[str, str]
    checks: list[LocalASRSmokeCheck]
    recommendation: str
    opens_microphone: bool = False
    downloads_models: bool = False
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
            "# Local ASR Smoke Pack",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Output directory: `{self.out_dir}`",
            f"- Opens microphone: `{str(self.opens_microphone).lower()}`",
            f"- Downloads models: `{str(self.downloads_models).lower()}`",
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
class LocalASRSmokeReport:
    status: str
    score: float
    generated_at: str
    audio_path: str
    out_dir: str
    mode: str
    checks: list[LocalASRSmokeCheck]
    artifacts: dict[str, str]
    metrics: dict[str, Any]
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
            "# Local ASR Smoke Run",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Mode: `{self.mode}`",
            f"- Audio: `{self.audio_path}`",
            f"- Output directory: `{self.out_dir}`",
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
        if self.metrics:
            lines.extend(["", "## Metrics", "", "| Metric | Value |", "|---|---|"])
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


def build_local_asr_smoke_pack(
    *,
    out_dir: str | Path,
    audio_path: str = "mic_alpha_live/audio.wav",
    sidecar_path: str = "mic_alpha_live/audio.transcript.txt",
    reference_path: str = "mic_alpha_live/audio.transcript.txt",
    model_size: str = "small",
    device: str = "cpu",
    smoke_dir: str = "local_asr_smoke",
) -> LocalASRSmokePackReport:
    """Create a local-ASR smoke pack without opening a microphone or downloading models."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scripts = out / "scripts"
    scripts.mkdir(exist_ok=True)

    commands = {
        "01_sidecar_smoke": (
            "PYTHONPATH=src python -m meeting_agent local-asr-smoke-run "
            f"--audio-path {audio_path} --sidecar {sidecar_path} --reference {reference_path} "
            f"--out-dir {smoke_dir} --mode sidecar"
        ),
        "02_faster_whisper_doctor": (
            "PYTHONPATH=src python -m meeting_agent asr-doctor "
            f"--provider faster-whisper --model-size {model_size} --device {device}"
        ),
        "03_faster_whisper_dry_run": (
            "PYTHONPATH=src python -m meeting_agent asr-validation-run "
            f"--audio-path {audio_path} --provider faster-whisper --model-size {model_size} "
            f"--device {device} --out-dir asr_validation_faster_whisper --dry-run"
        ),
        "04_faster_whisper_real_smoke": (
            "PYTHONPATH=src python -m meeting_agent asr-to-minutes "
            f"--audio-path {audio_path} --provider faster-whisper --model-size {model_size} "
            f"--device {device} --out-dir asr_minutes_faster_whisper"
        ),
        "05_smoke_gate": (
            "PYTHONPATH=src python -m meeting_agent local-asr-smoke-gate "
            f"--smoke-dir {smoke_dir} --real-asr-dir asr_minutes_faster_whisper "
            "--out-json local_asr_smoke_gate.json --out-md local_asr_smoke_gate.md"
        ),
    }

    artifacts: dict[str, str] = {}
    for name, command in commands.items():
        script = scripts / f"{name}.sh"
        script.write_text("#!/usr/bin/env bash\nset -euo pipefail\n\n" + command + "\n", encoding="utf-8")
        try:
            script.chmod(0o755)
        except OSError:
            pass
        artifacts[f"scripts/{script.name}"] = str(script)

    manifest = {
        "project": "ai-meeting-agent-community",
        "version": "2.0.0",
        "kind": "local_asr_smoke_pack",
        "created_for": "private_developer_preview",
        "opens_microphone": False,
        "downloads_models": False,
        "publication_hold": True,
        "private_core_included": False,
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
        "asr": {
            "audio_path": audio_path,
            "sidecar_path": sidecar_path,
            "reference_path": reference_path,
            "model_size": model_size,
            "device": device,
            "smoke_dir": smoke_dir,
        },
        "commands": commands,
    }
    _write_json(out / "local_asr_smoke_manifest.json", manifest)
    artifacts["local_asr_smoke_manifest.json"] = str(out / "local_asr_smoke_manifest.json")
    (out / "README.md").write_text(_pack_readme(manifest), encoding="utf-8")
    (out / "commands.md").write_text(_commands_markdown(commands), encoding="utf-8")
    (out / "operator_checklist.md").write_text(_operator_checklist(), encoding="utf-8")
    artifacts["README.md"] = str(out / "README.md")
    artifacts["commands.md"] = str(out / "commands.md")
    artifacts["operator_checklist.md"] = str(out / "operator_checklist.md")

    doctor = run_asr_doctor("faster-whisper", model_size=model_size, device=device)
    doctor_status = "warn" if doctor.status == "fail" else doctor.status
    checks = [
        LocalASRSmokeCheck("pack_created", "pass", "Local ASR smoke pack generated without recording or model download."),
        LocalASRSmokeCheck("sidecar_first", "pass", "Sidecar smoke command is included for deterministic validation."),
        LocalASRSmokeCheck("faster_whisper_doctor", doctor_status, doctor.recommendation, doctor.to_dict()),
        LocalASRSmokeCheck("publication_hold", "pass", "Publication remains blocked by policy."),
        LocalASRSmokeCheck("private_core_excluded", "pass", "Private Quality Engine is not included."),
    ]
    report = LocalASRSmokePackReport(
        status=_status(checks),
        score=_score(checks),
        out_dir=str(out),
        generated_at=utc_now_iso(),
        commands=commands,
        artifacts=artifacts,
        checks=checks,
        recommendation="Run sidecar smoke first, then faster-whisper doctor/dry-run, then one real local-ASR smoke on the captured WAV when dependencies are ready.",
        private_core_included=False,
    )
    _write_report(out, report, stem="local_asr_smoke_pack")
    artifacts["local_asr_smoke_pack.json"] = str(out / "local_asr_smoke_pack.json")
    artifacts["local_asr_smoke_pack.md"] = str(out / "local_asr_smoke_pack.md")
    return LocalASRSmokePackReport(report.status, report.score, report.out_dir, report.generated_at, report.commands, artifacts, report.checks, report.recommendation, False, False, True, False)


def run_local_asr_smoke(
    *,
    audio_path: str | Path,
    out_dir: str | Path,
    sidecar_path: str | Path | None = None,
    reference_path: str | Path | None = None,
    mode: str = "sidecar",
    model_size: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
    include_faster_whisper_doctor: bool = True,
    require_real_asr: bool = False,
    real_asr_report: str | Path | None = None,
) -> LocalASRSmokeReport:
    """Run a local-ASR smoke sequence on an existing WAV.

    The default mode is deterministic sidecar validation plus ASR-to-minutes.
    It does not open the microphone. It treats faster-whisper availability as a
    warning unless `require_real_asr` is set.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    audio = Path(audio_path)
    checks: list[LocalASRSmokeCheck] = []
    artifacts: dict[str, str] = {}
    metrics: dict[str, Any] = {}
    summary: dict[str, Any] = {"mode": mode, "provider": mode, "requires_real_asr": require_real_asr}

    if audio.exists():
        checks.append(LocalASRSmokeCheck("audio_path", "pass", f"Audio exists: {audio}"))
    else:
        checks.append(LocalASRSmokeCheck("audio_path", "fail", f"Audio is missing: {audio}"))

    if include_faster_whisper_doctor:
        doctor = run_asr_doctor("faster-whisper", model_size=model_size, device=device)
        doctor_status = "warn" if doctor.status == "fail" else doctor.status
        (out / "faster_whisper_doctor.json").write_text(doctor.to_json() + "\n", encoding="utf-8")
        artifacts["faster_whisper_doctor.json"] = str(out / "faster_whisper_doctor.json")
        checks.append(LocalASRSmokeCheck("faster_whisper_doctor", doctor_status, doctor.recommendation, doctor.to_dict()))
        summary["faster_whisper_doctor_status"] = doctor.status

    sidecar_ok = bool(sidecar_path and Path(sidecar_path).exists())
    if sidecar_ok:
        sidecar_dir = out / "sidecar_asr_validation"
        sidecar_report = run_asr_validation(
            audio_path=audio,
            out_dir=sidecar_dir,
            provider="sidecar",
            sidecar_path=sidecar_path,
            reference_path=reference_path or sidecar_path,
            meeting_id="mtg_local_asr_smoke_sidecar",
            title="Local ASR Smoke Sidecar",
        )
        artifacts["sidecar/asr_validation_report.json"] = str(sidecar_dir / "asr_validation_report.json")
        artifacts["sidecar/asr_validation_report.md"] = str(sidecar_dir / "asr_validation_report.md")
        checks.append(LocalASRSmokeCheck("sidecar_validation", sidecar_report.status, f"Sidecar ASR validation score {sidecar_report.score}.", sidecar_report.to_dict()))
        metrics.update({f"sidecar_{key}": value for key, value in sidecar_report.metrics.items()})
        summary["sidecar_status"] = sidecar_report.status
        summary["sidecar_segments"] = sidecar_report.summary.get("segments", 0)

        sidecar_minutes_dir = out / "sidecar_asr_minutes"
        sidecar_minutes = run_asr_to_minutes_workflow(
            audio_path=audio,
            out_dir=sidecar_minutes_dir,
            provider="sidecar",
            sidecar_path=sidecar_path,
            reference_path=reference_path or sidecar_path,
            meeting_id="mtg_local_asr_smoke_minutes",
            title="Local ASR Smoke Minutes",
        )
        artifacts["sidecar/asr_minutes_report.json"] = str(sidecar_minutes_dir / "asr_minutes_report.json")
        artifacts["sidecar/minutes.html"] = str(sidecar_minutes_dir / "minutes.html")
        checks.append(LocalASRSmokeCheck("sidecar_asr_to_minutes", sidecar_minutes.status, f"Sidecar ASR-to-minutes score {sidecar_minutes.score}.", sidecar_minutes.to_dict()))
        summary["sidecar_minutes_status"] = sidecar_minutes.status
        summary["sidecar_decisions"] = sidecar_minutes.summary.get("decisions", 0)
        summary["sidecar_action_items"] = sidecar_minutes.summary.get("action_items", 0)
    else:
        checks.append(LocalASRSmokeCheck("sidecar_validation", "warn", "No sidecar transcript found; deterministic sidecar smoke skipped."))

    real_status = None
    real_report_path = Path(real_asr_report) if real_asr_report else None
    if real_report_path and real_report_path.exists():
        real_status = _read_report_status(real_report_path)
        checks.append(LocalASRSmokeCheck("real_local_asr_report", "pass" if real_status == "pass" else "warn", f"Real local ASR report found with status={real_status}.", {"path": str(real_report_path)}))
        artifacts["real_local_asr_report"] = str(real_report_path)
    else:
        status = "fail" if require_real_asr else "warn"
        checks.append(LocalASRSmokeCheck("real_local_asr_report", status, "No faster-whisper real smoke artifact found yet. This is expected until Mac dependency validation runs."))
    summary["real_local_asr_status"] = real_status or "missing"

    checks.append(LocalASRSmokeCheck("publication_hold", "pass", "Publication remains intentionally blocked."))
    checks.append(LocalASRSmokeCheck("private_core_excluded", "pass", "Private Quality Engine is not used by local ASR smoke."))

    report = LocalASRSmokeReport(
        status=_status(checks),
        score=_score(checks),
        generated_at=utc_now_iso(),
        audio_path=str(audio),
        out_dir=str(out),
        mode=mode,
        checks=checks,
        artifacts=artifacts,
        metrics=metrics,
        summary=summary,
        recommendation=_run_recommendation(checks, require_real_asr),
        private_core_included=False,
    )
    write_local_asr_smoke_report(report, out_json=out / "local_asr_smoke_report.json", out_md=out / "local_asr_smoke_report.md")
    artifacts["local_asr_smoke_report.json"] = str(out / "local_asr_smoke_report.json")
    artifacts["local_asr_smoke_report.md"] = str(out / "local_asr_smoke_report.md")
    return LocalASRSmokeReport(report.status, report.score, report.generated_at, report.audio_path, report.out_dir, report.mode, report.checks, artifacts, report.metrics, report.summary, report.recommendation, True, False)


def evaluate_local_asr_smoke_gate(
    *,
    smoke_dir: str | Path,
    real_asr_dir: str | Path | None = None,
    require_real_asr: bool = False,
) -> LocalASRSmokeReport:
    smoke = Path(smoke_dir)
    checks: list[LocalASRSmokeCheck] = []
    artifacts: dict[str, str] = {}
    summary: dict[str, Any] = {"require_real_asr": require_real_asr}
    report_path = smoke / "local_asr_smoke_report.json"
    if report_path.exists():
        status = _read_report_status(report_path)
        artifacts["local_asr_smoke_report.json"] = str(report_path)
        checks.append(LocalASRSmokeCheck("local_asr_smoke_report", "pass" if status in {"pass", "warn"} else "fail", f"Local ASR smoke report found with status={status}."))
        summary["local_asr_smoke_status"] = status
    else:
        checks.append(LocalASRSmokeCheck("local_asr_smoke_report", "fail", f"Missing local ASR smoke report: {report_path}"))

    real_dir = Path(real_asr_dir) if real_asr_dir else None
    real_candidates = []
    if real_dir:
        real_candidates.extend([real_dir / "asr_minutes_report.json", real_dir / "asr_validation_report.json"])
    real_candidates.extend([smoke / "real_asr_report.json", smoke / "faster_whisper_asr_minutes_report.json"])
    real_found = next((path for path in real_candidates if path.exists()), None)
    if real_found:
        real_status = _read_report_status(real_found)
        artifacts["real_asr_report"] = str(real_found)
        checks.append(LocalASRSmokeCheck("real_asr_smoke", "pass" if real_status == "pass" else "warn", f"Real ASR smoke artifact found with status={real_status}."))
        summary["real_asr_status"] = real_status
    else:
        checks.append(LocalASRSmokeCheck("real_asr_smoke", "fail" if require_real_asr else "warn", "No faster-whisper real smoke artifact found yet."))
        summary["real_asr_status"] = "missing"

    checks.append(LocalASRSmokeCheck("publication_hold", "pass", "Publication remains blocked."))
    checks.append(LocalASRSmokeCheck("private_core_excluded", "pass", "Private Quality Engine is not included."))
    report = LocalASRSmokeReport(
        status=_status(checks),
        score=_score(checks),
        generated_at=utc_now_iso(),
        audio_path="",
        out_dir=str(smoke),
        mode="gate",
        checks=checks,
        artifacts=artifacts,
        metrics={},
        summary=summary,
        recommendation=_gate_recommendation(checks, require_real_asr),
        private_core_included=False,
    )
    return report


def write_local_asr_smoke_pack_report(report: LocalASRSmokePackReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        Path(out_json).write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        Path(out_md).write_text(report.to_markdown(), encoding="utf-8")


def write_local_asr_smoke_report(report: LocalASRSmokeReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        Path(out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(out_json).write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        Path(out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(out_md).write_text(report.to_markdown(), encoding="utf-8")


def _write_report(out: Path, report: Any, stem: str) -> None:
    (out / f"{stem}.json").write_text(report.to_json() + "\n", encoding="utf-8")
    (out / f"{stem}.md").write_text(report.to_markdown(), encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_report_status(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return str(payload.get("status") or payload.get("workflow", {}).get("status") or "") or None


def _status(checks: list[LocalASRSmokeCheck]) -> str:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "pass"


def _score(checks: list[LocalASRSmokeCheck]) -> float:
    if not checks:
        return 0.0
    total = 0.0
    for check in checks:
        total += 1.0 if check.status == "pass" else 0.62 if check.status == "warn" else 0.0
    return round(total / len(checks), 3)


def _run_recommendation(checks: list[LocalASRSmokeCheck], require_real_asr: bool) -> str:
    status = _status(checks)
    if status == "pass":
        return "Local ASR smoke passed. Keep publication on hold until launch assets and maintainer approval are complete."
    if require_real_asr:
        return "Real local ASR is required but not yet passing. Install optional ASR dependencies and run faster-whisper smoke on the captured WAV."
    return "Sidecar/local smoke is ready. Next, run one faster-whisper real smoke in the Python 3.12 environment when back at the Mac."


def _gate_recommendation(checks: list[LocalASRSmokeCheck], require_real_asr: bool) -> str:
    if _status(checks) == "pass":
        return "Local ASR smoke gate passed. Continue packaging/launch polish while publication remains blocked."
    if require_real_asr:
        return "Gate requires real ASR evidence. Run faster-whisper ASR-to-minutes and re-run this gate."
    return "Gate has warnings only because real ASR evidence is missing. This is acceptable for private preview but not for public announcement."


def _pack_readme(manifest: dict[str, Any]) -> str:
    return (
        "# Local ASR Smoke Pack\n\n"
        "This private developer-preview pack validates local ASR on a known WAV. "
        "It does not open the microphone, download models, or include private Quality Engine code.\n\n"
        "## Order\n\n"
        "1. Run sidecar smoke.\n"
        "2. Run faster-whisper doctor and dry-run.\n"
        "3. Install optional ASR dependencies in Python 3.12.\n"
        "4. Run one short faster-whisper real smoke on captured audio.\n"
        "5. Run the local ASR smoke gate.\n\n"
        f"Audio path: `{manifest['asr']['audio_path']}`\n"
    )


def _commands_markdown(commands: dict[str, str]) -> str:
    lines = ["# Local ASR Smoke Commands", ""]
    for name, command in commands.items():
        lines.extend([f"## {name}", "", "```bash", command, "```", ""])
    return "\n".join(lines)


def _operator_checklist() -> str:
    return (
        "# Local ASR Smoke Operator Checklist\n\n"
        "- [ ] Use a known short WAV first.\n"
        "- [ ] Confirm sidecar transcript aligns with the audio.\n"
        "- [ ] Run faster-whisper doctor before any model invocation.\n"
        "- [ ] Keep model caches and generated media out of git.\n"
        "- [ ] Review CER/WER and ASR-to-minutes HTML before public alpha.\n"
        "- [ ] Keep publication-gate on hold.\n"
    )


def _md(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
