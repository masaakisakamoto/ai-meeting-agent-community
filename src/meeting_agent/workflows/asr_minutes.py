from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent.core.transcript import load_transcript, save_transcript
from meeting_agent.exporters.csv_exporter import ActionItemCSVExporter
from meeting_agent.exporters.html import HTMLExporter
from meeting_agent.exporters.json_exporter import write_json
from meeting_agent.exporters.markdown import MarkdownExporter
from meeting_agent.intelligence.rule_minutes import RuleBasedMinutesGenerator
from meeting_agent.intelligence.verifier import MinutesVerifier
from meeting_agent.quality.gates import run_minutes_quality_gate, write_quality_gate_result
from meeting_agent.streaming.replay import write_replay_json, write_replay_ndjson
from meeting_agent.ui.demo_bundle import build_desktop_lite_bundle
from meeting_agent.workflows.asr_validation import run_asr_validation, write_asr_validation_run_report


@dataclass(frozen=True)
class ASRMinutesCheck:
    id: str
    status: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ASRMinutesReport:
    status: str
    score: float
    provider: str
    audio_path: str
    out_dir: str
    meeting_id: str
    title: str
    checks: list[ASRMinutesCheck]
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
            "# ASR to Minutes Workflow",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Provider: `{self.provider}`",
            f"- Audio: `{self.audio_path}`",
            f"- Output directory: `{self.out_dir}`",
            f"- Meeting ID: `{self.meeting_id}`",
            f"- Title: `{self.title}`",
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
            lines.extend(["", "## ASR Metrics", "", "| Metric | Value |", "|---|---|"])
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


def run_asr_to_minutes_workflow(
    *,
    audio_path: str | Path,
    out_dir: str | Path,
    provider: str = "sidecar",
    sidecar_path: str | Path | None = None,
    reference_path: str | Path | None = None,
    meeting_id: str = "mtg_asr_minutes",
    title: str = "ASR to Minutes",
    model_size: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
    dry_run: bool = False,
) -> ASRMinutesReport:
    """Run ASR validation and turn the generated transcript into evidence-linked minutes.

    This is a public Community workflow. It intentionally uses the existing ASR
    provider abstraction and the basic rule-based minutes generator. It never
    imports or requires the private Quality Engine.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    audio = Path(audio_path)
    checks: list[ASRMinutesCheck] = []
    artifacts: dict[str, str] = {}

    asr_dir = out / "asr_validation"
    asr_report = run_asr_validation(
        audio_path=audio,
        out_dir=asr_dir,
        provider=provider,
        sidecar_path=sidecar_path,
        reference_path=reference_path,
        meeting_id=meeting_id,
        title=title,
        model_size=model_size,
        device=device,
        compute_type=compute_type,
        dry_run=dry_run,
    )
    write_asr_validation_run_report(asr_report, out_json=out / "asr_validation_report.json", out_md=out / "asr_validation_report.md")
    artifacts["asr_validation_report.json"] = str(out / "asr_validation_report.json")
    artifacts["asr_validation_report.md"] = str(out / "asr_validation_report.md")
    for name, path in asr_report.artifacts.items():
        artifacts[f"asr/{name}"] = path
    checks.append(ASRMinutesCheck("asr_validation", asr_report.status, f"ASR validation completed with score {asr_report.score}.", asr_report.to_dict()))

    transcript_path = asr_dir / "transcript.asr.json"
    if dry_run:
        checks.append(ASRMinutesCheck("dry_run", "pass", "Dry-run stopped before minutes generation."))
        report = ASRMinutesReport(
            status=_status(checks),
            score=_score(checks),
            provider=provider,
            audio_path=str(audio),
            out_dir=str(out),
            meeting_id=meeting_id,
            title=title,
            checks=checks,
            artifacts=artifacts,
            metrics=asr_report.metrics,
            summary={"dry_run": True, "private_core_included": False},
            recommendation="Dry-run complete. Run without --dry-run after ASR dependencies and sidecar/reference paths are ready.",
            private_core_included=False,
        )
        _write_report(out, report)
        return report

    if not transcript_path.exists():
        checks.append(ASRMinutesCheck("transcript", "fail", f"ASR transcript was not generated: {transcript_path}"))
        report = ASRMinutesReport(
            status="fail",
            score=_score(checks),
            provider=provider,
            audio_path=str(audio),
            out_dir=str(out),
            meeting_id=meeting_id,
            title=title,
            checks=checks,
            artifacts=artifacts,
            metrics=asr_report.metrics,
            summary={"dry_run": False, "private_core_included": False},
            recommendation="Resolve ASR validation errors before generating minutes.",
            private_core_included=False,
        )
        _write_report(out, report)
        return report

    transcript = load_transcript(transcript_path)
    save_transcript(transcript, out / "meeting_from_asr.json")
    artifacts["meeting_from_asr.json"] = str(out / "meeting_from_asr.json")
    checks.append(ASRMinutesCheck("transcript", "pass" if transcript.segments else "warn", f"Loaded {len(transcript.segments)} ASR transcript segments."))

    minutes = RuleBasedMinutesGenerator().generate(transcript)
    verification = MinutesVerifier().verify(transcript, minutes)
    quality = run_minutes_quality_gate(transcript, minutes, verification)
    write_json(minutes, out / "minutes.json")
    MarkdownExporter().export(transcript, minutes, out / "minutes.md")
    HTMLExporter().export(transcript, minutes, out / "minutes.html")
    ActionItemCSVExporter().export(transcript, minutes, out / "action_items.csv")
    write_json(verification, out / "verification.json")
    write_quality_gate_result(quality, out / "quality_gate.json")
    write_replay_json(transcript, out / "replay_events.json")
    write_replay_ndjson(transcript, out / "replay_events.ndjson")
    build_desktop_lite_bundle(
        transcript,
        out / "desktop_lite",
        minutes=minutes,
        desktop_alpha={"asr_to_minutes": {"status": "pass", "provider": provider, "private_core_included": False}},
        bridge_enabled=True,
        bridge_url="http://127.0.0.1:8765",
    )
    artifacts.update(
        {
            "minutes.json": str(out / "minutes.json"),
            "minutes.md": str(out / "minutes.md"),
            "minutes.html": str(out / "minutes.html"),
            "action_items.csv": str(out / "action_items.csv"),
            "verification.json": str(out / "verification.json"),
            "quality_gate.json": str(out / "quality_gate.json"),
            "replay_events.json": str(out / "replay_events.json"),
            "replay_events.ndjson": str(out / "replay_events.ndjson"),
            "desktop_lite": str(out / "desktop_lite" / "index.html"),
        }
    )
    checks.append(ASRMinutesCheck("minutes", "pass", f"Generated {len(minutes.decisions)} decisions, {len(minutes.action_items)} actions, {len(minutes.open_questions)} open questions."))
    checks.append(ASRMinutesCheck("verification", verification.status, f"Verification score {verification.score}; issues {len(verification.issues)}."))
    checks.append(ASRMinutesCheck("quality_gate", quality.status, f"Quality score {quality.score}."))
    checks.append(ASRMinutesCheck("private_core_excluded", "pass", "Private Quality Engine is not used by the Community ASR-to-minutes workflow."))

    summary = {
        "segments": len(transcript.segments),
        "decisions": len(minutes.decisions),
        "action_items": len(minutes.action_items),
        "open_questions": len(minutes.open_questions),
        "risks": len(minutes.risks),
        "verification_status": verification.status,
        "quality_status": quality.status,
        "quality_score": quality.score,
        "asr_cer": asr_report.metrics.get("cer"),
        "asr_wer": asr_report.metrics.get("wer"),
        "private_core_included": False,
    }
    status = _status(checks)
    recommendation = (
        "ASR transcript has been converted to evidence-linked minutes. Review HTML evidence and CER/WER before relying on the notes."
        if status in {"pass", "warn"}
        else "Fix ASR or grounding issues before using these minutes."
    )
    report = ASRMinutesReport(status, _score(checks), provider, str(audio), str(out), meeting_id, title, checks, artifacts, asr_report.metrics, summary, recommendation, False)
    _write_report(out, report)
    return report


def write_asr_minutes_report(report: ASRMinutesReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def _write_report(out: Path, report: ASRMinutesReport) -> None:
    (out / "asr_minutes_report.json").write_text(report.to_json() + "\n", encoding="utf-8")
    (out / "asr_minutes_report.md").write_text(report.to_markdown(), encoding="utf-8")


def _status(checks: list[ASRMinutesCheck]) -> str:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "pass"


def _score(checks: list[ASRMinutesCheck]) -> float:
    if not checks:
        return 0.0
    total = 0.0
    for check in checks:
        total += 1.0 if check.status == "pass" else 0.55 if check.status == "warn" else 0.0
    return round(total / len(checks), 3)


def _md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")
