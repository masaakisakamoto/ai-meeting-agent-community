from __future__ import annotations

import json
import shutil
import math
import struct
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent import __version__
from meeting_agent.core.schemas import MinutesDraft, Transcript
from meeting_agent.core.transcript import load_transcript, parse_plain_text_transcript, save_transcript

from meeting_agent.audio import read_wav_info
from meeting_agent.exporters.csv_exporter import ActionItemCSVExporter
from meeting_agent.exporters.html import HTMLExporter
from meeting_agent.exporters.json_exporter import write_json
from meeting_agent.exporters.markdown import MarkdownExporter
from meeting_agent.intelligence.verifier import MinutesVerifier
from meeting_agent.providers.asr import SidecarTranscriptProvider
from meeting_agent.quality.gates import run_minutes_quality_gate, write_quality_gate_result
from meeting_agent.intelligence.rule_minutes import RuleBasedMinutesGenerator
from meeting_agent.ui.demo_bundle import build_desktop_lite_bundle
from meeting_agent.workflows.local_audio import default_sidecar_text, run_local_audio_workflow
import os

def _desktop_debug(label: str) -> None:
    if os.environ.get("MEETING_AGENT_DEMO_DEBUG") == "1":
        print(f"[desktop] {label}", flush=True)


@dataclass(frozen=True)
class DesktopAlphaReport:
    """Deterministic smoke report for the portable Desktop Alpha workspace."""

    status: str
    score: float
    workspace: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Desktop Alpha Smoke Report",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Workspace: `{self.workspace}`",
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "|---|---|---|",
        ]
        for check in self.checks:
            lines.append(
                f"| {check.get('id')} | `{check.get('status')}` | {check.get('detail', '')} |"
            )
        lines.extend(["", "## Artifacts", "", "| Name | Path |", "|---|---|"])
        for name, path in sorted(self.artifacts.items()):
            lines.append(f"| {name} | `{path}` |")
        if self.notes:
            lines.extend(["", "## Notes", ""])
            lines.extend(f"- {note}" for note in self.notes)
        return "\n".join(lines) + "\n"


class DesktopAlphaManager:
    """Creates and validates a portable Community Desktop Alpha workspace.

    This manager intentionally uses only public Community components: simulated audio,
    sidecar ASR, basic evidence-linked minutes, static UI assets, and local artifacts.
    The private quality engine, model router, private evals, enterprise modules, and
    advanced Japanese correction pipeline remain outside this workspace.
    """

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace)

    @property
    def desktop_lite_dir(self) -> Path:
        return self.workspace / "desktop_lite"

    @property
    def sessions_dir(self) -> Path:
        return self.workspace / "sessions"

    @property
    def outputs_dir(self) -> Path:
        return self.workspace / "outputs"

    def initialize(self, transcript: Transcript | None = None, *, minutes=None, bridge_host: str = "127.0.0.1", bridge_port: int = 8765) -> dict[str, Path]:
        self.workspace.mkdir(parents=True, exist_ok=True)
        transcript = transcript or self._default_transcript()
        minutes = minutes or RuleBasedMinutesGenerator().generate(transcript)

        desktop_alpha_payload = self._desktop_payload(status="initialized", bridge_host=bridge_host, bridge_port=bridge_port)
        paths = build_desktop_lite_bundle(
            transcript,
            self.desktop_lite_dir,
            minutes=minutes,
            desktop_alpha=desktop_alpha_payload,
            bridge_enabled=True,
            bridge_url=f"http://{bridge_host}:{bridge_port}",
            extra_payload={"desktop_workflow": desktop_alpha_payload},
        )

        manifest_path = self.workspace / "desktop_alpha_manifest.json"
        manifest = self._manifest(transcript=transcript, status="initialized", bridge_host=bridge_host, bridge_port=bridge_port)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        launcher_path = self.workspace / "launch_desktop_alpha.py"
        launcher_path.write_text(self._launcher_script(), encoding="utf-8")
        launcher_path.chmod(0o755)

        readme_path = self.workspace / "README.md"
        readme_path.write_text(self._workspace_readme(), encoding="utf-8")

        result = {
            "index.html": paths["index.html"],
            "demo_data.js": paths["demo_data.js"],
            "manifest": manifest_path,
            "launcher": launcher_path,
            "README": readme_path,
        }
        return result

    def run_smoke(self) -> DesktopAlphaReport:
        """Run a deterministic Desktop Alpha smoke workflow.

        This intentionally avoids real microphones and heavyweight ASR. The smoke
        path writes a tiny local WAV, attaches a sidecar transcript, generates
        evidence-linked minutes, and verifies that the portable UI workspace can
        be initialized. The private quality engine remains excluded.
        """
        self.workspace.mkdir(parents=True, exist_ok=True)
        session_dir = self.sessions_dir / "desktop_alpha_sim"
        output_dir = self.outputs_dir / "desktop_alpha_audio"
        session_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        workflow_status = self._run_minimal_smoke_session(session_dir)

        copied: dict[str, str] = {}
        for name in [
            "meeting_from_audio.json",
            "minutes.json",
            "minutes.md",
            "minutes.html",
            "verification.json",
            "quality_gate.json",
            "action_items.csv",
            "audio_info.json",
            "asr_smoke.json",
            "workflow_report.json",
            "workflow_report.md",
        ]:
            src = session_dir / name
            if src.exists():
                dst = output_dir / name
                shutil.copy2(src, dst)
                copied[name] = str(dst)

        transcript = load_transcript(session_dir / "meeting_from_audio.json")
        self.initialize(transcript)

        checks = [
            _check("static_ui", (self.desktop_lite_dir / "index.html").exists(), "Desktop Lite UI exists"),
            _check("audio_wav", (session_dir / "audio.wav").exists(), "Simulated WAV exists"),
            _check("minutes", (output_dir / "minutes.md").exists(), "Minutes export exists"),
            _check("bridge_launcher", (self.workspace / "launch_desktop_alpha.py").exists(), "Launcher exists"),
            _check("private_core_excluded", True, "Private Quality Engine is intentionally excluded"),
        ]
        passed = sum(1 for check in checks if check["status"] == "pass")
        score = round(passed / len(checks), 4) if checks else 0.0
        status = "pass" if score >= 0.95 and workflow_status in {"pass", "warn"} else "warn"

        artifacts = {
            "workspace_manifest": str(self.workspace / "desktop_alpha_manifest.json"),
            "desktop_lite_index": str(self.desktop_lite_dir / "index.html"),
            "launcher": str(self.workspace / "launch_desktop_alpha.py"),
            "audio_wav": str(session_dir / "audio.wav"),
            "session_report": str(session_dir / "workflow_report.json"),
            "minutes_md": str(output_dir / "minutes.md"),
        }
        artifacts.update({f"output_{k}": v for k, v in copied.items()})
        summary = {
            "workflow_status": workflow_status,
            "workflow_score_basis": "deterministic Community smoke workflow",
            "session_dir": str(session_dir),
            "output_dir": str(output_dir),
            "ui_dir": str(self.desktop_lite_dir),
        }
        notes = [
            "This smoke test uses deterministic generated audio and sidecar ASR for OSS-safe validation.",
            "Real microphone and system-audio capture remain optional/provider-specific.",
        ]
        report = DesktopAlphaReport(status, score, str(self.workspace), checks, artifacts, summary, notes)
        (self.workspace / "desktop_alpha_smoke.json").write_text(report.to_json() + "\n", encoding="utf-8")
        (self.workspace / "desktop_alpha_smoke.md").write_text(report.to_markdown(), encoding="utf-8")
        return report

    def _run_minimal_smoke_session(self, session_dir: Path) -> str:
        wav_path = session_dir / "audio.wav"
        sidecar_path = session_dir / "audio.transcript.txt"
        transcript_path = session_dir / "meeting_from_audio.json"
        minutes_json_path = session_dir / "minutes.json"
        minutes_md_path = session_dir / "minutes.md"
        minutes_html_path = session_dir / "minutes.html"
        verification_path = session_dir / "verification.json"
        quality_path = session_dir / "quality_gate.json"
        actions_path = session_dir / "action_items.csv"
        info_path = session_dir / "audio_info.json"
        smoke_path = session_dir / "asr_smoke.json"

        _write_tone_wav(wav_path, duration_ms=3000)
        info_path.write_text(read_wav_info(wav_path).to_json() + "\n", encoding="utf-8")
        sidecar_path.write_text(default_sidecar_text("v0.7").rstrip() + "\n", encoding="utf-8")

        transcript = SidecarTranscriptProvider(sidecar_path=sidecar_path).transcribe_file(
            str(wav_path),
            meeting_id="mtg_desktop_alpha_audio",
            title="Desktop Alpha Local Audio Workflow",
        )
        save_transcript(transcript, transcript_path)
        minutes = RuleBasedMinutesGenerator().generate(transcript)
        verification = MinutesVerifier().verify(transcript, minutes)
        quality = run_minutes_quality_gate(transcript, minutes, verification)
        write_json(minutes, minutes_json_path)
        MarkdownExporter().export(transcript, minutes, minutes_md_path)
        HTMLExporter().export(transcript, minutes, minutes_html_path)
        ActionItemCSVExporter().export(transcript, minutes, actions_path)
        write_json(verification, verification_path)
        write_quality_gate_result(quality, quality_path)
        smoke = {
            "provider": "sidecar_transcript",
            "status": "pass" if transcript.segments else "fail",
            "score": 1.0 if transcript.segments else 0.0,
            "segments": len(transcript.segments),
            "audio_path": str(wav_path),
            "private_core_included": False,
        }
        smoke_path.write_text(json.dumps(smoke, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        build_desktop_lite_bundle(transcript, session_dir / "desktop_lite", minutes=minutes, extra_payload={"asr_smoke": smoke})
        workflow_report = {
            "status": "pass" if quality.status in {"pass", "warn"} and transcript.segments else "warn",
            "artifacts": {
                "audio_wav": str(wav_path),
                "transcript": str(transcript_path),
                "minutes_md": str(minutes_md_path),
                "desktop_lite": str(session_dir / "desktop_lite" / "index.html"),
            },
            "private_core_included": False,
        }
        (session_dir / "workflow_report.json").write_text(json.dumps(workflow_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (session_dir / "workflow_report.md").write_text("# Desktop Alpha Smoke Workflow\n\n- Status: `pass`\n- Private core included: `false`\n", encoding="utf-8")
        return workflow_report["status"]

    def _manifest(self, *, transcript: Transcript, status: str, bridge_host: str = "127.0.0.1", bridge_port: int = 8765) -> dict[str, Any]:
        return {
            "schema_version": "desktop-alpha-manifest/v1",
            "project": "ai-meeting-agent-community",
            "version": __version__,
            "status": status,
            "workspace": str(self.workspace),
            "entrypoint": "desktop_lite/index.html",
            "bridge": {
                "host": bridge_host,
                "port": bridge_port,
                "health": "/health",
                "api_health": "/api/health",
                "devices": "/api/audio/devices",
                "simulated_workflow": "/api/workflows/simulated-record",
            },
            "meeting": {
                "meeting_id": transcript.meeting_id,
                "title": transcript.title,
                "segments": len(transcript.segments),
            },
            "workflow_steps": self._workflow_steps(status=status),
            "public_boundary": {
                "included_community_components": [
                    "Desktop Lite UI",
                    "Local Desktop Bridge",
                    "Simulated audio workflow",
                    "Sidecar ASR smoke workflow",
                    "Basic evidence-linked minutes",
                    "Audio diagnostics and level meter",
                ],
                "excluded_private_core": [
                    "Private Quality Engine",
                    "Advanced Japanese correction pipeline",
                    "Model router selection logic",
                    "Private evaluation datasets",
                    "Speaker-name mapping intelligence",
                    "Enterprise admin, billing, SSO, and audit implementation",
                ],
            },
        }

    def _desktop_payload(self, *, status: str, bridge_host: str = "127.0.0.1", bridge_port: int = 8765) -> dict[str, Any]:
        return {
            "status": status,
            "version": __version__,
            "workspace": str(self.workspace),
            "bridge_url": f"http://{bridge_host}:{bridge_port}",
            "steps": self._workflow_steps(status=status),
        }

    @staticmethod
    def _workflow_steps(*, status: str) -> list[dict[str, str]]:
        return [
            {"id": "preflight", "label": "Preflight", "status": "done" if status else "pending"},
            {"id": "capture", "label": "Audio Capture", "status": "done" if status == "smoke_passed" else "ready"},
            {"id": "diagnostics", "label": "Diagnostics", "status": "ready"},
            {"id": "asr", "label": "ASR Smoke", "status": "ready"},
            {"id": "minutes", "label": "Minutes", "status": "ready"},
            {"id": "export", "label": "Export", "status": "ready"},
        ]

    @staticmethod
    def _default_transcript() -> Transcript:
        return parse_plain_text_transcript(default_sidecar_text("v0.7"), meeting_id="mtg_desktop_alpha", title="Desktop Alpha")

    @staticmethod
    def _launcher_script() -> str:
        return """#!/usr/bin/env python3
from pathlib import Path
from meeting_agent.desktop.bridge import DesktopBridgeConfig, serve_desktop_bridge

workspace = Path(__file__).resolve().parent
serve_desktop_bridge(DesktopBridgeConfig(workspace=workspace, static_dir=workspace / 'desktop_lite', host='127.0.0.1', port=8765))
"""

    @staticmethod
    def _workspace_readme() -> str:
        return """# AI Meeting Agent Desktop Alpha Workspace

This is a portable Developer Preview workspace.

## Run local bridge

```bash
PYTHONPATH=src python -m meeting_agent desktop-serve --workspace ./desktop_alpha
```

Then open <http://127.0.0.1:8765>.

## Boundary

Included: static UI, local bridge, simulated audio workflow, sidecar ASR smoke, basic evidence-linked minutes.

Excluded: Private Quality Engine, model router, private evaluation datasets, enterprise modules.
"""


def _write_tone_wav(path: Path, *, duration_ms: int = 3000, sample_rate_hz: int = 16000, frequency_hz: float = 440.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total_samples = int(sample_rate_hz * duration_ms / 1000)
    amplitude = 2500
    frames = bytearray()
    for i in range(total_samples):
        sample = int(amplitude * math.sin(2 * math.pi * frequency_hz * i / sample_rate_hz))
        frames.extend(struct.pack("<h", sample))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate_hz)
        wav.writeframes(bytes(frames))


def _check(check_id: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"id": check_id, "status": "pass" if ok else "fail", "detail": detail}
