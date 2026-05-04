from __future__ import annotations

import json
import platform
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent.core.schemas import utc_now_iso
from meeting_agent.release.publication import run_publication_gate


@dataclass(frozen=True)
class EvidenceCheck:
    id: str
    status: str
    detail: str
    category: str = "evidence"
    required_for_public_alpha: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceCollectionPackReport:
    status: str
    score: float
    out_dir: str
    generated_at: str
    commands: dict[str, str]
    artifacts: dict[str, str]
    checks: list[EvidenceCheck]
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
            "# Real Mac Evidence Collection Pack",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Output directory: `{self.out_dir}`",
            f"- Opens microphone: `{str(self.opens_microphone).lower()}`",
            f"- Publication hold: `{str(self.publication_hold).lower()}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            f"- Generated at: `{self.generated_at}`",
            "",
            "## Purpose",
            "",
            "This pack helps collect the final private evidence needed before a public alpha announcement: real Mac microphone capture, post-capture minutes, local ASR smoke, launch assets, screenshots, and release gates. Generating this pack does not open the microphone.",
            "",
            "## Commands",
            "",
        ]
        for name, command in self.commands.items():
            lines.extend([f"### {name}", "", "```bash", command, "```", ""])
        lines.extend(["## Checks", "", "| Check | Status | Required | Detail |", "|---|---|---:|---|"])
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | `{str(check.required_for_public_alpha).lower()}` | {_md(check.detail)} |")
        lines.extend(["", "## Artifacts", "", "| Name | Path |", "|---|---|"])
        for name, path in sorted(self.artifacts.items()):
            lines.append(f"| {name} | `{path}` |")
        lines.extend(["", "## Recommendation", "", self.recommendation, ""])
        return "\n".join(lines)


@dataclass(frozen=True)
class EvidenceCollectionReport:
    status: str
    score: float
    generated_at: str
    root: str
    evidence_dir: str
    checks: list[EvidenceCheck]
    artifacts: dict[str, str]
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
            "# Real Mac Evidence Collection",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Root: `{self.root}`",
            f"- Evidence directory: `{self.evidence_dir}`",
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
        lines.extend(["", "## Checks", "", "| Check | Status | Required | Category | Detail |", "|---|---|---:|---|---|"])
        for check in self.checks:
            lines.append(
                f"| {check.id} | `{check.status}` | `{str(check.required_for_public_alpha).lower()}` | {check.category} | {_md(check.detail)} |"
            )
        lines.extend(["", "## Collected artifacts", "", "| Name | Path |", "|---|---|"])
        for name, path in sorted(self.artifacts.items()):
            lines.append(f"| {name} | `{path}` |")
        lines.extend(["", "## Recommendation", "", self.recommendation, ""])
        return "\n".join(lines)


def build_real_mac_evidence_pack(
    *,
    out_dir: str | Path,
    root: str | Path = ".",
    mic_dir: str = "mic_alpha_live",
    minutes_dir: str = "mic_minutes_live",
    asr_minutes_dir: str = "asr_minutes_faster_whisper",
    local_asr_dir: str = "local_asr_smoke",
    launch_assets_dir: str = "launch_assets",
    evidence_dir: str = "real_mac_evidence",
    duration_ms: int = 3000,
    device_id: str = "microphone:default",
) -> EvidenceCollectionPackReport:
    """Generate a private evidence collection pack without opening the microphone."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scripts = out / "scripts"
    scripts.mkdir(exist_ok=True)

    commands = {
        "01_env_and_publication_gates": (
            "PYTHONPATH=src python -m meeting_agent dev-env-doctor --root . --out-json dev_environment.json --out-md dev_environment.md\n"
            "PYTHONPATH=src python -m meeting_agent publication-gate --root . --out-json publication_gate.json --out-md publication_gate.md\n"
            "PYTHONPATH=src python -m meeting_agent public-alpha-readiness --root . --out-json public_alpha_readiness.json --out-md public_alpha_readiness.md"
        ),
        "02_real_mic_capture": (
            "PYTHONPATH=src python -m meeting_agent record-microphone-alpha "
            f"--out-dir {mic_dir} --duration-ms {duration_ms} --device-id {device_id} "
            "--live --confirm-live-recording --notice-acknowledged --participants-notified"
        ),
        "03_sidecar_template": (
            f"cp {out}/sidecar_template.txt {mic_dir}/audio.transcript.txt\n"
            "echo 'Edit the transcript template so it matches your recorded speech before sidecar validation.'"
        ),
        "04_post_capture_minutes": (
            "PYTHONPATH=src python -m meeting_agent microphone-to-minutes "
            f"--mic-dir {mic_dir} --out-dir {minutes_dir} --provider sidecar"
        ),
        "05_local_asr_smoke": (
            "PYTHONPATH=src python -m meeting_agent local-asr-smoke-run "
            f"--audio-path {mic_dir}/audio.wav --sidecar {mic_dir}/audio.transcript.txt "
            f"--reference {mic_dir}/audio.transcript.txt --out-dir {local_asr_dir} --mode sidecar\n"
            "PYTHONPATH=src python -m meeting_agent asr-to-minutes "
            f"--audio-path {mic_dir}/audio.wav --provider faster-whisper --model-size small --device cpu --out-dir {asr_minutes_dir}"
        ),
        "06_capture_and_asr_gates": (
            "PYTHONPATH=src python -m meeting_agent real-capture-execution-gate "
            f"--mic-dir {mic_dir} --minutes-dir {minutes_dir} --asr-minutes-dir {asr_minutes_dir} "
            "--out-json real_capture_execution_gate.json --out-md real_capture_execution_gate.md\n"
            "PYTHONPATH=src python -m meeting_agent local-asr-smoke-gate "
            f"--smoke-dir {local_asr_dir} --real-asr-dir {asr_minutes_dir} "
            "--out-json local_asr_smoke_gate.json --out-md local_asr_smoke_gate.md"
        ),
        "07_launch_assets": (
            f"PYTHONPATH=src python -m meeting_agent launch-assets-pack --out-dir {launch_assets_dir}\n"
            f"PYTHONPATH=src python -m meeting_agent launch-assets-gate --assets-dir {launch_assets_dir} --demo-dir demo_out --out-json launch_assets_gate.json --out-md launch_assets_gate.md"
        ),
        "08_collect_evidence": (
            "PYTHONPATH=src python -m meeting_agent real-mac-evidence-collect "
            f"--root . --evidence-dir {evidence_dir} --mic-dir {mic_dir} --minutes-dir {minutes_dir} "
            f"--asr-minutes-dir {asr_minutes_dir} --local-asr-dir {local_asr_dir} --launch-assets-dir {launch_assets_dir} "
            "--out-json real_mac_evidence.json --out-md real_mac_evidence.md"
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
        "kind": "real_mac_evidence_collection_pack",
        "created_for": "private_developer_preview",
        "opens_microphone": False,
        "publication_hold": True,
        "private_core_included": False,
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
        "inputs": {
            "root": str(root),
            "mic_dir": mic_dir,
            "minutes_dir": minutes_dir,
            "asr_minutes_dir": asr_minutes_dir,
            "local_asr_dir": local_asr_dir,
            "launch_assets_dir": launch_assets_dir,
            "evidence_dir": evidence_dir,
            "duration_ms": duration_ms,
            "device_id": device_id,
        },
        "commands": commands,
    }
    _write_json(out / "real_mac_evidence_manifest.json", manifest)
    artifacts["real_mac_evidence_manifest.json"] = str(out / "real_mac_evidence_manifest.json")

    (out / "README.md").write_text(_pack_readme(manifest), encoding="utf-8")
    (out / "commands.md").write_text(_commands_markdown(commands), encoding="utf-8")
    (out / "operator_checklist.md").write_text(_operator_checklist(), encoding="utf-8")
    (out / "screenshot_shotlist.md").write_text(_screenshot_shotlist(), encoding="utf-8")
    (out / "sidecar_template.txt").write_text(_sidecar_template(), encoding="utf-8")
    for filename in ["README.md", "commands.md", "operator_checklist.md", "screenshot_shotlist.md", "sidecar_template.txt"]:
        artifacts[filename] = str(out / filename)

    checks = [
        EvidenceCheck("pack_created", "pass", "Real Mac evidence collection pack generated without opening the microphone."),
        EvidenceCheck("publication_hold", "pass", "Publication remains blocked until the maintainer explicitly flips policy."),
        EvidenceCheck("private_core_excluded", "pass", "Private Quality Engine is not included."),
        EvidenceCheck("live_capture_requires_explicit_action", "pass", "Live capture is only present inside a clearly labeled script and requires consent flags."),
        EvidenceCheck("screenshot_plan", "pass", "Screenshot shotlist is included for later launch polish."),
    ]
    report = EvidenceCollectionPackReport(
        status=_status(checks),
        score=_score(checks),
        out_dir=str(out),
        generated_at=utc_now_iso(),
        commands=commands,
        artifacts=artifacts,
        checks=checks,
        recommendation="Run this pack on the Mac after Python 3.12/audio dependencies are ready. Keep publication-gate on hold until real capture, local ASR smoke, screenshots, and launch assets are all verified.",
    )
    write_real_mac_evidence_pack_report(report, out_json=out / "real_mac_evidence_pack.json", out_md=out / "real_mac_evidence_pack.md")
    artifacts["real_mac_evidence_pack.json"] = str(out / "real_mac_evidence_pack.json")
    artifacts["real_mac_evidence_pack.md"] = str(out / "real_mac_evidence_pack.md")
    return EvidenceCollectionPackReport(report.status, report.score, report.out_dir, report.generated_at, report.commands, artifacts, report.checks, report.recommendation)


def collect_real_mac_evidence(
    *,
    root: str | Path = ".",
    evidence_dir: str | Path = "real_mac_evidence",
    mic_dir: str | Path = "mic_alpha_live",
    minutes_dir: str | Path = "mic_minutes_live",
    asr_minutes_dir: str | Path = "asr_minutes_faster_whisper",
    local_asr_dir: str | Path = "local_asr_smoke",
    launch_assets_dir: str | Path = "launch_assets",
    copy_artifacts: bool = True,
) -> EvidenceCollectionReport:
    root_path = Path(root)
    out = Path(evidence_dir)
    if not out.is_absolute():
        out = root_path / out
    out.mkdir(parents=True, exist_ok=True)
    screenshots = out / "screenshots"
    screenshots.mkdir(exist_ok=True)
    collected = out / "collected"
    if copy_artifacts:
        collected.mkdir(exist_ok=True)

    mic = _resolve(root_path, mic_dir)
    minutes = _resolve(root_path, minutes_dir)
    asr_minutes = _resolve(root_path, asr_minutes_dir)
    local_asr = _resolve(root_path, local_asr_dir)
    launch_assets = _resolve(root_path, launch_assets_dir)

    publication = run_publication_gate(root_path)
    checks: list[EvidenceCheck] = [
        EvidenceCheck("publication_hold", "pass" if publication.status == "hold" else "fail", f"publication-gate status={publication.status}", "publication", True, {"blocked_modes": publication.blocked_modes}),
        EvidenceCheck("private_core_excluded", "pass", "No private core artifacts are expected in Community evidence.", "commercial_guardrail", True),
    ]
    artifacts: dict[str, str] = {}

    def check_file(id_: str, path: Path, detail: str, category: str, required: bool = True, copy_as: str | None = None) -> None:
        exists = path.exists() and path.is_file()
        checks.append(EvidenceCheck(id_, "pass" if exists else "warn", detail if exists else f"Missing: {path}", category, required, {"path": str(path)}))
        if exists:
            artifacts[id_] = str(path)
            if copy_artifacts and copy_as:
                target = collected / copy_as
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(path, target)
                    artifacts[f"collected/{id_}"] = str(target)
                except OSError:
                    pass

    check_file("audio_wav", mic / "audio.wav", "Real microphone WAV found.", "hardware", True, "mic_audio.wav")
    check_file("recording_safety_gate", mic / "recording_safety_gate.json", "Recording safety gate artifact found.", "safety", True, "recording_safety_gate.json")
    check_file("audit_log", mic / "audit.jsonl", "Audit log found.", "audit", True, "audit.jsonl")
    check_file("microphone_alpha_report", mic / "microphone_alpha.json", "Microphone alpha report found.", "hardware", True, "microphone_alpha.json")
    check_file("audio_quality", mic / "audio_quality.json", "Audio quality report found.", "quality", True, "audio_quality.json")
    check_file("audio_levels", mic / "audio_levels.md", "Audio level report found.", "quality", False, "audio_levels.md")
    check_file("post_capture_minutes_html", minutes / "minutes.html", "Post-capture minutes HTML found.", "minutes", True, "mic_minutes.html")
    check_file("post_capture_report", minutes / "microphone_minutes_report.json", "Post-capture workflow report found.", "minutes", False, "microphone_minutes_report.json")
    check_file("asr_minutes_report", asr_minutes / "asr_minutes_report.json", "ASR-to-minutes report found.", "asr", True, "asr_minutes_report.json")
    check_file("asr_minutes_html", asr_minutes / "minutes.html", "ASR-to-minutes HTML found.", "asr", False, "asr_minutes.html")
    check_file("local_asr_smoke_report", local_asr / "local_asr_smoke_report.json", "Local ASR smoke report found.", "asr", True, "local_asr_smoke_report.json")
    check_file("launch_readme_draft", launch_assets / "README_PUBLIC_ALPHA_DRAFT.md", "Launch README draft found.", "launch", False, "README_PUBLIC_ALPHA_DRAFT.md")
    check_file("launch_known_limitations", launch_assets / "KNOWN_LIMITATIONS.md", "Known limitations draft found.", "launch", False, "KNOWN_LIMITATIONS.md")

    # Gate reports can live at the root after the operator scripts run.
    for id_, filename, detail, category in [
        ("real_capture_execution_gate", "real_capture_execution_gate.json", "Real capture execution gate report found.", "gate"),
        ("local_asr_smoke_gate", "local_asr_smoke_gate.json", "Local ASR smoke gate report found.", "gate"),
        ("launch_assets_gate", "launch_assets_gate.json", "Launch assets gate report found.", "gate"),
        ("public_alpha_readiness", "public_alpha_readiness.json", "Public alpha readiness report found.", "gate"),
    ]:
        check_file(id_, root_path / filename, detail, category, False, filename)

    screenshot_files = list(screenshots.glob("*.png")) + list(screenshots.glob("*.jpg")) + list(screenshots.glob("*.jpeg"))
    checks.append(EvidenceCheck(
        "screenshots",
        "pass" if len(screenshot_files) >= 3 else "warn",
        f"{len(screenshot_files)} screenshot(s) found. Add at least 3 before public alpha." if screenshot_files else "No screenshots found yet. Place launch screenshots in real_mac_evidence/screenshots/.",
        "launch",
        False,
        {"count": len(screenshot_files)},
    ))
    for i, shot in enumerate(screenshot_files[:20], start=1):
        artifacts[f"screenshot_{i}"] = str(shot)

    status = _status(checks)
    score = _score(checks)
    required_missing = [check.id for check in checks if check.required_for_public_alpha and check.status != "pass"]
    summary = {
        "required_missing": required_missing,
        "artifact_count": len(artifacts),
        "screenshot_count": len(screenshot_files),
        "publication_status": publication.status,
        "ready_for_public_alpha": not required_missing and len(screenshot_files) >= 3,
    }
    recommendation = (
        "Evidence looks close. Review screenshots and launch drafts, then keep publication-gate on hold until the maintainer explicitly authorizes public release."
        if not required_missing else
        "Collect the missing required artifacts before public alpha: " + ", ".join(required_missing)
    )
    report = EvidenceCollectionReport(
        status=status,
        score=score,
        generated_at=utc_now_iso(),
        root=str(root_path),
        evidence_dir=str(out),
        checks=checks,
        artifacts=artifacts,
        summary=summary,
        recommendation=recommendation,
    )
    write_real_mac_evidence_report(report, out_json=out / "real_mac_evidence.json", out_md=out / "real_mac_evidence.md")
    (out / "evidence_index.json").write_text(report.to_json() + "\n", encoding="utf-8")
    (out / "evidence_index.md").write_text(report.to_markdown(), encoding="utf-8")
    return report


def write_real_mac_evidence_pack_report(report: EvidenceCollectionPackReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        Path(out_json).write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        Path(out_md).write_text(report.to_markdown(), encoding="utf-8")


def write_real_mac_evidence_report(report: EvidenceCollectionReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        Path(out_json).write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        Path(out_md).write_text(report.to_markdown(), encoding="utf-8")


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _status(checks: list[EvidenceCheck]) -> str:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "pass"


def _score(checks: list[EvidenceCheck]) -> float:
    if not checks:
        return 1.0
    weights = {"pass": 1.0, "warn": 0.55, "fail": 0.0}
    return round(sum(weights.get(check.status, 0.0) for check in checks) / len(checks), 3)


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _commands_markdown(commands: dict[str, str]) -> str:
    lines = ["# Real Mac Evidence Commands", ""]
    for name, command in commands.items():
        lines.extend([f"## {name}", "", "```bash", command, "```", ""])
    return "\n".join(lines)


def _pack_readme(manifest: dict[str, Any]) -> str:
    return f"""# Real Mac Evidence Collection Pack

This private pack collects the evidence needed before a public alpha announcement.

- Opens microphone during pack generation: `{str(manifest['opens_microphone']).lower()}`
- Publication hold: `{str(manifest['publication_hold']).lower()}`
- Private core included: `{str(manifest['private_core_included']).lower()}`

## Recommended order

1. Run `scripts/01_env_and_publication_gates.sh`.
2. Run `scripts/02_real_mic_capture.sh` only when you are ready to record and have notified participants.
3. Edit `sidecar_template.txt` and copy it into the capture directory.
4. Run post-capture minutes and local-ASR scripts.
5. Add screenshots to `real_mac_evidence/screenshots/`.
6. Run `scripts/08_collect_evidence.sh`.

Do not publish the repository or announce publicly until publication policy is explicitly changed.
"""


def _operator_checklist() -> str:
    return """# Real Mac Evidence Operator Checklist

- [ ] Python 3.12 virtual environment is active.
- [ ] `pip install -e \".[audio,asr]\"` has completed.
- [ ] Recording notice has been shown to all participants.
- [ ] Recording duration is short and controlled for alpha validation.
- [ ] `mic_alpha_live/audio.wav` exists.
- [ ] `mic_minutes_live/minutes.html` exists.
- [ ] `asr_minutes_faster_whisper/asr_minutes_report.json` exists.
- [ ] At least 3 screenshots are placed in `real_mac_evidence/screenshots/`.
- [ ] `publication-gate` still reports `hold`.
"""


def _screenshot_shotlist() -> str:
    return """# Screenshot Shotlist

Capture these screenshots before public alpha review:

1. Desktop Alpha UI with `Bridge Connected`.
2. Evidence-linked HTML minutes.
3. Audio readiness / level report.
4. Real capture execution gate result.
5. Local ASR smoke result.
6. Public alpha readiness still on hold.

Save them under `real_mac_evidence/screenshots/`.
"""


def _sidecar_template() -> str:
    return """[00:00:00-00:00:05] Operator: This is a short microphone validation recording for the AI Meeting Agent private alpha.
[00:00:05-00:00:10] Operator: The goal is to validate capture, audio quality, ASR handoff, and evidence-linked minutes.
[00:00:10-00:00:15] Operator: We will keep publication on hold until all gates pass.
"""
