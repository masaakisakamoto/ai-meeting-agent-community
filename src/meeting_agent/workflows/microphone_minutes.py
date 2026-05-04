from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent.audio import analyze_audio_levels, analyze_wav_quality, read_wav_info, write_audio_level_report
from meeting_agent.core.transcript import save_transcript
from meeting_agent.exporters.csv_exporter import ActionItemCSVExporter
from meeting_agent.exporters.html import HTMLExporter
from meeting_agent.exporters.json_exporter import write_json
from meeting_agent.exporters.markdown import MarkdownExporter
from meeting_agent.intelligence.rule_minutes import RuleBasedMinutesGenerator
from meeting_agent.intelligence.verifier import MinutesVerifier
from meeting_agent.providers.asr import FasterWhisperProvider, SidecarTranscriptProvider
from meeting_agent.quality.gates import run_minutes_quality_gate, write_quality_gate_result
from meeting_agent.streaming.replay import write_replay_json, write_replay_ndjson
from meeting_agent.ui.demo_bundle import build_desktop_lite_bundle
from meeting_agent.workflows.local_audio import default_sidecar_text


@dataclass(frozen=True)
class PostCaptureCheck:
    id: str
    status: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PostCaptureGateReport:
    status: str
    score: float
    mic_dir: str
    audio_path: str | None
    provider: str
    checks: list[PostCaptureCheck]
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
            "# Post-Capture Gate",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Microphone directory: `{self.mic_dir}`",
            f"- Audio path: `{self.audio_path or 'missing'}`",
            f"- ASR provider: `{self.provider}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "|---|---|---|",
        ]
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | {_md(check.detail)} |")
        lines.extend(["", "## Recommendation", "", self.recommendation, ""])
        return "\n".join(lines)


@dataclass(frozen=True)
class MicrophoneMinutesReport:
    status: str
    score: float
    mode: str
    mic_dir: str
    out_dir: str
    audio_path: str | None
    provider: str
    meeting_id: str
    title: str
    summary: dict[str, Any]
    checks: list[PostCaptureCheck]
    artifacts: dict[str, str] = field(default_factory=dict)
    recommendation: str = ""
    gate: dict[str, Any] = field(default_factory=dict)
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Microphone to Minutes Workflow",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Mode: `{self.mode}`",
            f"- ASR provider: `{self.provider}`",
            f"- Microphone directory: `{self.mic_dir}`",
            f"- Output directory: `{self.out_dir}`",
            f"- Audio path: `{self.audio_path or 'missing'}`",
            f"- Meeting ID: `{self.meeting_id}`",
            f"- Title: `{self.title}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            "",
            "## Summary",
            "",
        ]
        for key, value in self.summary.items():
            lines.append(f"- {key}: `{value}`")
        lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "|---|---|---|"])
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | {_md(check.detail)} |")
        lines.extend(["", "## Artifacts", "", "| Name | Path |", "|---|---|"])
        for name, path in sorted(self.artifacts.items()):
            lines.append(f"| {name} | `{path}` |")
        lines.extend(["", "## Recommendation", "", self.recommendation, ""])
        return "\n".join(lines)


def evaluate_post_capture_gate(
    mic_dir: str | Path,
    *,
    audio_path: str | Path | None = None,
    provider: str = "sidecar",
    sidecar_path: str | Path | None = None,
) -> PostCaptureGateReport:
    mic = Path(mic_dir)
    audio = _resolve_audio_path(mic, audio_path)
    sidecar = _resolve_sidecar_path(mic, sidecar_path)
    checks: list[PostCaptureCheck] = []
    checks.append(PostCaptureCheck("mic_dir", "pass" if mic.exists() else "warn", "Microphone directory exists." if mic.exists() else "Microphone directory does not exist yet; only explicit audio_path can be used."))
    if audio and audio.exists():
        checks.append(PostCaptureCheck("audio_wav", "pass", f"Audio WAV found: {audio}"))
        try:
            info = read_wav_info(audio)
            checks.append(PostCaptureCheck("audio_info", "pass", f"{info.duration_ms} ms / {info.sample_rate_hz} Hz / {info.channels} channel(s)", info.to_dict()))
            quality = analyze_wav_quality(audio)
            checks.append(PostCaptureCheck("audio_quality", quality.status, f"Quality score {quality.score}; RMS {quality.rms_dbfs} dBFS", quality.to_dict()))
        except Exception as exc:
            checks.append(PostCaptureCheck("audio_readable", "fail", f"Could not inspect audio: {exc}"))
    else:
        checks.append(PostCaptureCheck("audio_wav", "fail", "No audio.wav found. Run microphone alpha real capture or provide --audio-path."))
    if provider == "sidecar":
        checks.append(PostCaptureCheck("sidecar_transcript", "pass" if sidecar and sidecar.exists() else "warn", f"Sidecar transcript found: {sidecar}" if sidecar and sidecar.exists() else "No sidecar transcript found; workflow will create a deterministic developer-preview sidecar unless one is supplied."))
    elif provider == "faster-whisper":
        checks.append(PostCaptureCheck("local_asr_provider", "warn", "faster-whisper execution is optional and environment-dependent. Run asr-doctor before using real local ASR."))
    else:
        checks.append(PostCaptureCheck("asr_provider", "fail", f"Unsupported ASR provider: {provider}"))
    checks.append(PostCaptureCheck("private_core_excluded", "pass", "Private Quality Engine is not used by the Community post-capture workflow."))
    status = _status(checks)
    recommendation = (
        "Post-capture workflow can run. Use sidecar for deterministic validation, or install local ASR dependencies for faster-whisper."
        if status in {"pass", "warn"}
        else "Resolve failed post-capture checks before generating minutes."
    )
    return PostCaptureGateReport(status, _score(checks), str(mic), str(audio) if audio else None, provider, checks, recommendation, False)


def write_post_capture_gate_report(report: PostCaptureGateReport, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def run_microphone_to_minutes_workflow(
    *,
    mic_dir: str | Path,
    out_dir: str | Path,
    audio_path: str | Path | None = None,
    provider: str = "sidecar",
    sidecar_path: str | Path | None = None,
    meeting_id: str = "mtg_microphone_alpha",
    title: str = "Microphone Alpha Minutes",
    model_size: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
) -> MicrophoneMinutesReport:
    mic = Path(mic_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    audio = _resolve_audio_path(mic, audio_path)
    gate = evaluate_post_capture_gate(mic, audio_path=audio, provider=provider, sidecar_path=sidecar_path)
    write_post_capture_gate_report(gate, out_json=out / "post_capture_gate.json", out_md=out / "post_capture_gate.md")
    checks: list[PostCaptureCheck] = list(gate.checks)
    artifacts: dict[str, str] = {"post_capture_gate.json": str(out / "post_capture_gate.json"), "post_capture_gate.md": str(out / "post_capture_gate.md")}
    if not audio or not audio.exists():
        report = MicrophoneMinutesReport(
            "fail",
            gate.score,
            "post_capture_missing_audio",
            str(mic),
            str(out),
            str(audio) if audio else None,
            provider,
            meeting_id,
            title,
            {"private_core_included": False},
            checks,
            artifacts,
            "No audio file is available. Run real microphone alpha capture first, or provide --audio-path.",
            gate.to_dict(),
            False,
        )
        write_microphone_minutes_report(report, out_json=out / "microphone_minutes_report.json", out_md=out / "microphone_minutes_report.md")
        return report

    # Copy the source audio into the post-capture output so the workflow folder is self-contained.
    copied_audio = out / "audio.wav"
    if audio.resolve() != copied_audio.resolve():
        shutil.copy2(audio, copied_audio)
    artifacts["audio.wav"] = str(copied_audio)
    info = read_wav_info(copied_audio)
    (out / "audio_info.json").write_text(info.to_json() + "\n", encoding="utf-8")
    artifacts["audio_info.json"] = str(out / "audio_info.json")
    quality = analyze_wav_quality(copied_audio)
    (out / "audio_quality.json").write_text(quality.to_json() + "\n", encoding="utf-8")
    artifacts["audio_quality.json"] = str(out / "audio_quality.json")
    levels = analyze_audio_levels(copied_audio, window_ms=100)
    write_audio_level_report(levels, out / "audio_levels.json", out / "audio_levels.md")
    artifacts["audio_levels.json"] = str(out / "audio_levels.json")
    artifacts["audio_levels.md"] = str(out / "audio_levels.md")

    if provider == "sidecar":
        sidecar = _ensure_sidecar(mic, out, sidecar_path)
        artifacts["audio.transcript.txt"] = str(sidecar)
        asr_provider = SidecarTranscriptProvider(sidecar_path=sidecar)
        mode = "sidecar_post_capture"
    elif provider == "faster-whisper":
        asr_provider = FasterWhisperProvider(model_size=model_size, device=device, compute_type=compute_type)
        mode = "local_asr_post_capture"
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    transcript = asr_provider.transcribe_file(str(copied_audio), meeting_id=meeting_id, title=title)
    save_transcript(transcript, out / "meeting_from_microphone.json")
    artifacts["meeting_from_microphone.json"] = str(out / "meeting_from_microphone.json")
    write_replay_json(transcript, out / "replay_events.json")
    write_replay_ndjson(transcript, out / "replay_events.ndjson")
    artifacts["replay_events.json"] = str(out / "replay_events.json")
    artifacts["replay_events.ndjson"] = str(out / "replay_events.ndjson")

    minutes = RuleBasedMinutesGenerator().generate(transcript)
    verification = MinutesVerifier().verify(transcript, minutes)
    quality_gate = run_minutes_quality_gate(transcript, minutes, verification)
    write_json(minutes, out / "minutes.json")
    MarkdownExporter().export(transcript, minutes, out / "minutes.md")
    HTMLExporter().export(transcript, minutes, out / "minutes.html")
    ActionItemCSVExporter().export(transcript, minutes, out / "action_items.csv")
    write_json(verification, out / "verification.json")
    write_quality_gate_result(quality_gate, out / "quality_gate.json")
    artifacts.update({
        "minutes.json": str(out / "minutes.json"),
        "minutes.md": str(out / "minutes.md"),
        "minutes.html": str(out / "minutes.html"),
        "action_items.csv": str(out / "action_items.csv"),
        "verification.json": str(out / "verification.json"),
        "quality_gate.json": str(out / "quality_gate.json"),
    })

    asr_smoke = {
        "provider": provider,
        "status": "pass" if transcript.segments else "fail",
        "score": 1.0 if transcript.segments else 0.0,
        "segments": len(transcript.segments),
        "audio_path": str(copied_audio),
        "private_core_included": False,
    }
    (out / "asr_smoke.json").write_text(json.dumps(asr_smoke, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    artifacts["asr_smoke.json"] = str(out / "asr_smoke.json")

    build_desktop_lite_bundle(
        transcript,
        out / "desktop_lite",
        minutes=minutes,
        audio_diagnostics=quality.to_dict(),
        asr_smoke=asr_smoke,
        audio_levels=levels.to_dict(),
        desktop_alpha={
            "bridge_url": "http://127.0.0.1:8765",
            "microphone_minutes": {"status": "pass", "provider": provider, "segments": len(transcript.segments)},
            "post_capture_gate": gate.to_dict(),
        },
        bridge_enabled=True,
        bridge_url="http://127.0.0.1:8765",
    )
    artifacts["desktop_lite"] = str(out / "desktop_lite" / "index.html")

    checks.append(PostCaptureCheck("transcript", "pass" if transcript.segments else "fail", f"Generated {len(transcript.segments)} segment(s)."))
    checks.append(PostCaptureCheck("minutes", quality_gate.status, f"Quality gate {quality_gate.status}; verification {verification.status}."))
    checks.append(PostCaptureCheck("audio_quality_after_copy", quality.status, f"Audio quality {quality.status}; score {quality.score}."))
    status = _status(checks)
    if status == "pass" and quality_gate.status != "pass":
        status = "warn"
    summary = {
        "audio_duration_ms": info.duration_ms,
        "audio_quality_status": quality.status,
        "transcript_segments": len(transcript.segments),
        "decisions": len(minutes.decisions),
        "action_items": len(minutes.action_items),
        "open_questions": len(minutes.open_questions),
        "verification_status": verification.status,
        "quality_gate": quality_gate.status,
        "private_core_included": False,
    }
    recommendation = "Post-capture minutes are ready for review. Inspect evidence links before sharing." if status in {"pass", "warn"} else "Review failed checks before using the generated minutes."
    report = MicrophoneMinutesReport(status, _score(checks), mode, str(mic), str(out), str(copied_audio), provider, meeting_id, title, summary, checks, artifacts, recommendation, gate.to_dict(), False)
    write_microphone_minutes_report(report, out_json=out / "microphone_minutes_report.json", out_md=out / "microphone_minutes_report.md")
    return report


def write_microphone_minutes_report(report: MicrophoneMinutesReport, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def _resolve_audio_path(mic_dir: Path, audio_path: str | Path | None) -> Path | None:
    if audio_path:
        return Path(audio_path)
    candidates = [
        mic_dir / "audio.wav",
        mic_dir / "mic_alpha_out" / "audio.wav",
        mic_dir / "microphone_alpha" / "audio.wav",
        mic_dir / "local_audio_workflow" / "audio.wav",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _resolve_sidecar_path(mic_dir: Path, sidecar_path: str | Path | None) -> Path | None:
    if sidecar_path:
        return Path(sidecar_path)
    candidates = [
        mic_dir / "audio.transcript.txt",
        mic_dir / "mic_alpha_out" / "audio.transcript.txt",
        mic_dir / "microphone_alpha" / "audio.transcript.txt",
        mic_dir / "local_audio_workflow" / "audio.transcript.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _ensure_sidecar(mic_dir: Path, out: Path, sidecar_path: str | Path | None) -> Path:
    existing = _resolve_sidecar_path(mic_dir, sidecar_path)
    if existing and existing.exists():
        target = out / "audio.transcript.txt"
        if existing.resolve() != target.resolve():
            shutil.copy2(existing, target)
        return target
    target = out / "audio.transcript.txt"
    target.write_text(default_sidecar_text("v1.4").rstrip() + "\n", encoding="utf-8")
    return target


def _status(checks: list[PostCaptureCheck]) -> str:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "pass"


def _score(checks: list[PostCaptureCheck]) -> float:
    score = 1.0
    for check in checks:
        if check.status == "warn":
            score -= 0.08
        elif check.status == "fail":
            score -= 0.24
    return round(max(0.0, score), 3)


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
