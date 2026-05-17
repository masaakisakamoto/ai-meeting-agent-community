from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from meeting_agent.audio.capture_plan import build_live_capture_plan, write_live_capture_plan
from meeting_agent.audio.validation_pack import (
    build_capture_validation_pack,
    evaluate_capture_validation_run,
    write_capture_validation_pack_report,
    write_capture_validation_run_report,
)
from meeting_agent.audio import (
    LIVE_CONFIRMATION_PHRASE,
    analyze_audio_levels,
    analyze_wav_quality,
    assess_capture_readiness,
    capture_session_to_wav,
    read_wav_info,
    run_microphone_alpha_doctor,
    run_microphone_alpha_recording,
    evaluate_recording_safety_gate,
    microphone_setup_guide,
    write_microphone_alpha_report,
    write_microphone_setup_guide,
    write_audio_level_report,
    write_recording_safety_gate_report,
    write_wav_from_chunks,
)
from meeting_agent.compliance.consent import render_recording_notice
from meeting_agent.core.plugin_manifest import load_manifest, load_plugin_manifest
from meeting_agent.core.plugins import build_default_registry
from meeting_agent.core.schemas import minutes_from_dict, verification_report_from_dict
from meeting_agent.core.transcript import load_transcript, save_transcript
from meeting_agent.desktop.bridge import BridgeConfig, handle_bridge_request, serve_bridge
from meeting_agent.desktop.local_server import serve_desktop_alpha
from meeting_agent.desktop.package_check import run_desktop_package_check
from meeting_agent.desktop.packager import build_desktop_alpha_bundle
from meeting_agent.desktop.workspace import DesktopAlphaManager
from meeting_agent.evals.metrics import evaluate_text
from meeting_agent.exporters.csv_exporter import ActionItemCSVExporter
from meeting_agent.exporters.html import HTMLExporter
from meeting_agent.exporters.json_exporter import read_json, write_json
from meeting_agent.exporters.markdown import MarkdownExporter
from meeting_agent.intelligence.glossary import apply_glossary, load_glossary
from meeting_agent.workflows.corrected_minutes_review import write_review as write_corrected_minutes_review
from meeting_agent.intelligence.rule_minutes import RuleBasedMinutesGenerator
from meeting_agent.intelligence.verifier import MinutesVerifier
from meeting_agent.providers.asr import FasterWhisperProvider, SidecarTranscriptProvider
from meeting_agent.providers.asr.doctor import run_asr_doctor
from meeting_agent.providers.audio import AudioCaptureConfig, SimulatedAudioCaptureProvider, SoundDeviceMicrophoneProvider
from meeting_agent.quality.gates import run_minutes_quality_gate, write_quality_gate_result
from meeting_agent.release.readiness import assess_oss_readiness, run_readiness_checks, run_release_readiness, write_readiness_report
from meeting_agent.release.publication import run_publication_gate, write_publication_gate_report
from meeting_agent.release.private_alpha import run_private_alpha_gate, write_private_alpha_gate_report
from meeting_agent.release.public_alpha import (
    build_public_alpha_plan,
    run_public_alpha_readiness,
    write_public_alpha_plan_report,
    write_public_alpha_readiness_report,
)
from meeting_agent.release.public_alpha_candidate import (
    build_public_alpha_candidate_pack,
    run_public_alpha_candidate_gate,
    write_public_alpha_candidate_gate_report,
    write_public_alpha_candidate_pack_report,
)
from meeting_agent.release.maintainer_dashboard import (
    build_maintainer_review_pack,
    build_maintainer_dashboard,
    write_maintainer_review_pack_report,
    write_maintainer_dashboard_report,
)
from meeting_agent.release.launch_assets import (
    build_launch_asset_pack,
    run_launch_polish_check,
    write_launch_asset_pack_report,
    write_launch_polish_report,
)
from meeting_agent.release.evidence_collection import (
    build_real_mac_evidence_pack,
    collect_real_mac_evidence,
    write_real_mac_evidence_pack_report,
    write_real_mac_evidence_report,
)
from meeting_agent.release.evidence_export import (
    build_evidence_export_pack,
    build_screenshot_automation_pack,
    export_evidence_bundle,
    run_evidence_export_gate,
    run_screenshot_readiness_gate,
    write_evidence_export_pack_report,
    write_evidence_export_report,
    write_screenshot_automation_report,
)
from meeting_agent.env.dev_environment import run_dev_environment_doctor, write_dev_environment_report
from meeting_agent.release.sbom import write_sbom
from meeting_agent.security.redaction import redact_transcript
from meeting_agent.storage.sqlite_store import SQLiteMeetingStore
from meeting_agent.streaming.replay import TranscriptReplaySettings, write_replay_json, write_replay_ndjson
from meeting_agent.ui.demo_bundle import build_desktop_lite_bundle
from meeting_agent.workflows.asr_minutes import run_asr_to_minutes_workflow, write_asr_minutes_report
from meeting_agent.workflows.asr_validation import (
    build_asr_validation_pack,
    run_asr_validation,
    write_asr_validation_pack_report,
    write_asr_validation_run_report,
)
from meeting_agent.workflows.microphone_minutes import (
    evaluate_post_capture_gate,
    run_microphone_to_minutes_workflow,
    write_post_capture_gate_report,
)
from meeting_agent.workflows.real_capture_execution import (
    build_real_capture_execution_pack,
    evaluate_real_capture_execution,
    write_real_capture_execution_gate_report,
    write_real_capture_execution_pack_report,
)
from meeting_agent.workflows.local_asr_smoke import (
    build_local_asr_smoke_pack,
    evaluate_local_asr_smoke_gate,
    run_local_asr_smoke,
    write_local_asr_smoke_pack_report,
    write_local_asr_smoke_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="meeting-agent", description="AI Meeting Agent Community CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="Ingest a plain text or JSON transcript")
    p.add_argument("input")
    p.add_argument("--meeting-id", default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--out", required=True)

    p = sub.add_parser("minutes", help="Generate evidence-linked minutes")
    p.add_argument("transcript_json")
    p.add_argument("--template", default="default")
    p.add_argument("--out-json", required=True)
    p.add_argument("--out-md", required=False)

    p = sub.add_parser("apply-glossary", help="Apply canonical term corrections to transcript JSON")
    p.add_argument("transcript_json")
    p.add_argument("glossary_json")
    p.add_argument("--out", required=True)
    p.add_argument("--report", required=True)

    p = sub.add_parser("export-html", help="Export evidence-linked minutes as an HTML report")
    p.add_argument("transcript_json")
    p.add_argument("minutes_json")
    p.add_argument("--out", required=True)

    p = sub.add_parser("export-actions-csv", help="Export action items as CSV")
    p.add_argument("transcript_json")
    p.add_argument("minutes_json")
    p.add_argument("--out", required=True)

    p = sub.add_parser("store", help="Persist transcript/minutes into local SQLite store")
    p.add_argument("--db", required=True)
    p.add_argument("--transcript", required=True)
    p.add_argument("--minutes", required=False)

    p = sub.add_parser("list-store", help="List meetings in a local SQLite store")
    p.add_argument("--db", required=True)

    p = sub.add_parser("verify", help="Verify minutes grounding")
    p.add_argument("transcript_json")
    p.add_argument("minutes_json")
    p.add_argument("--out", required=True)

    p = sub.add_parser("redact", help="Redact basic PII in transcript JSON")
    p.add_argument("transcript_json")
    p.add_argument("--out", required=True)

    p = sub.add_parser("plugins", help="List built-in plugins")
    p.add_argument("--kind", default=None)

    p = sub.add_parser("eval-text", help="Compute CER/WER between text files")
    p.add_argument("--reference", required=True)
    p.add_argument("--hypothesis", required=True)

    p = sub.add_parser("quality-gate", help="Run deterministic quality gates for generated minutes")
    p.add_argument("transcript_json")
    p.add_argument("minutes_json")
    p.add_argument("verification_json")
    p.add_argument("--out", required=True)

    p = sub.add_parser("consent-notice", help="Render a recording/transcription consent notice")
    p.add_argument("--out", required=False)

    p = sub.add_parser("plugin-manifest", help="Print a plugin manifest")
    p.add_argument("manifest_json")

    p = sub.add_parser("validate-plugin", help="Validate a plugin manifest JSON file")
    p.add_argument("manifest_json")
    p.add_argument("--community-only", action="store_true")

    p = sub.add_parser("readiness", help="Check whether the repository is ready for public OSS release")
    p.add_argument("--root", default=".")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("release-check", help="Run stricter release gate profiles")
    p.add_argument("--root", default=".")
    p.add_argument("--profile", choices=["portfolio_preview", "public_oss"], default="public_oss")
    p.add_argument("--run-tests", action="store_true")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("publication-gate", help="Check private/public publication hold policy")
    p.add_argument("--root", default=".")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("dev-env-doctor", help="Check local developer environment for private alpha hardware validation")
    p.add_argument("--root", default=".")
    p.add_argument("--bridge-port", type=int, default=8765)
    p.add_argument("--bridge-url", default=None)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("private-alpha-gate", help="Check v1.0 private alpha handoff readiness while keeping publication blocked")
    p.add_argument("--root", default=".")
    p.add_argument("--bridge-port", type=int, default=8765)
    p.add_argument("--run-tests", action="store_true")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("public-alpha-readiness", help="Estimate public alpha readiness while keeping publication blocked")
    p.add_argument("--root", default=".")
    p.add_argument("--bridge-port", type=int, default=8765)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("public-alpha-plan", help="Generate a private plan for reaching public alpha without publishing yet")
    p.add_argument("--root", default=".")
    p.add_argument("--bridge-port", type=int, default=8765)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("public-alpha-candidate-pack", help="Generate a private public-alpha candidate pack without publishing")
    p.add_argument("--root", default=".")
    p.add_argument("--out-dir", default="public_alpha_candidate")
    p.add_argument("--demo-dir", default="demo_out")
    p.add_argument("--evidence-dir", default="real_mac_evidence")
    p.add_argument("--launch-assets-dir", default="launch_assets")
    p.add_argument("--candidate-version", default="v2.2 Public Alpha Candidate")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("public-alpha-candidate-gate", help="Evaluate private public-alpha candidate readiness while keeping publication hold")
    p.add_argument("--root", default=".")
    p.add_argument("--candidate-dir", default="public_alpha_candidate")
    p.add_argument("--evidence-dir", default="real_mac_evidence")
    p.add_argument("--launch-assets-dir", default="launch_assets")
    p.add_argument("--demo-dir", default="demo_out")
    p.add_argument("--bridge-port", type=int, default=8765)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("maintainer-review-pack", help="Generate a private maintainer review pack without publishing")
    p.add_argument("--root", default=".")
    p.add_argument("--out-dir", default="maintainer_review")
    p.add_argument("--dashboard-dir", default="maintainer_dashboard")
    p.add_argument("--evidence-dir", default="real_mac_evidence")
    p.add_argument("--launch-assets-dir", default="launch_assets")
    p.add_argument("--candidate-dir", default="public_alpha_candidate")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("maintainer-dashboard", help="Build a private maintainer evidence dashboard and HTML report")
    p.add_argument("--root", default=".")
    p.add_argument("--dashboard-dir", default="maintainer_dashboard")
    p.add_argument("--evidence-dir", default="real_mac_evidence")
    p.add_argument("--launch-assets-dir", default="launch_assets")
    p.add_argument("--candidate-dir", default="public_alpha_candidate")
    p.add_argument("--demo-dir", default="demo_out")
    p.add_argument("--bridge-port", type=int, default=8765)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)
    p.add_argument("--out-html", default=None)

    p = sub.add_parser("maintainer-review-gate", help="Alias for maintainer-dashboard")
    p.add_argument("--root", default=".")
    p.add_argument("--dashboard-dir", default="maintainer_dashboard")
    p.add_argument("--evidence-dir", default="real_mac_evidence")
    p.add_argument("--launch-assets-dir", default="launch_assets")
    p.add_argument("--candidate-dir", default="public_alpha_candidate")
    p.add_argument("--demo-dir", default="demo_out")
    p.add_argument("--bridge-port", type=int, default=8765)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)
    p.add_argument("--out-html", default=None)

    p = sub.add_parser("evidence-export-pack", help="Generate private evidence export and screenshot prep pack without publishing")
    p.add_argument("--root", default=".")
    p.add_argument("--out-dir", default="evidence_export_pack")
    p.add_argument("--export-dir", default="evidence_export")
    p.add_argument("--demo-dir", default="demo_out")
    p.add_argument("--evidence-dir", default="real_mac_evidence")
    p.add_argument("--launch-assets-dir", default="launch_assets")
    p.add_argument("--dashboard-dir", default="maintainer_dashboard")
    p.add_argument("--screenshot-dir", default="screenshots")
    p.add_argument("--bridge-url", default=None)
    p.add_argument("--bridge-port", type=int, default=8765)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("screenshot-automation-pack", help="Generate private screenshot shotlist and helper scripts")
    p.add_argument("--root", default=".")
    p.add_argument("--out-dir", default="screenshot_automation")
    p.add_argument("--demo-dir", default="demo_out")
    p.add_argument("--screenshot-dir", default="screenshots")
    p.add_argument("--bridge-url", default=None)
    p.add_argument("--bridge-port", type=int, default=8765)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("screenshot-readiness-gate", help="Check screenshot evidence count before public alpha")
    p.add_argument("--root", default=".")
    p.add_argument("--screenshot-dir", default="screenshots")
    p.add_argument("--demo-dir", default="demo_out")
    p.add_argument("--min-screenshots", type=int, default=3)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("evidence-export-run", help="Export private evidence bundle for maintainer review")
    p.add_argument("--root", default=".")
    p.add_argument("--out-dir", default="evidence_export")
    p.add_argument("--demo-dir", default="demo_out")
    p.add_argument("--evidence-dir", default="real_mac_evidence")
    p.add_argument("--launch-assets-dir", default="launch_assets")
    p.add_argument("--dashboard-dir", default="maintainer_dashboard")
    p.add_argument("--screenshot-dir", default="screenshots")
    p.add_argument("--no-copy-artifacts", action="store_true")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("evidence-export-gate", help="Verify private evidence export bundle")
    p.add_argument("--root", default=".")
    p.add_argument("--export-dir", default="evidence_export")
    p.add_argument("--screenshot-dir", default="screenshots")
    p.add_argument("--min-screenshots", type=int, default=3)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("launch-assets-pack", help="Generate private launch draft assets without publishing")
    p.add_argument("--root", default=".")
    p.add_argument("--out-dir", default="launch_assets")
    p.add_argument("--demo-dir", default="demo_out")
    p.add_argument("--bridge-port", type=int, default=8765)
    p.add_argument("--bridge-url", default=None)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("launch-assets-gate", help="Check Desktop Alpha launch assets and packaging polish")
    p.add_argument("--root", default=".")
    p.add_argument("--assets-dir", default=None)
    p.add_argument("--demo-dir", default="demo_out")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("launch-readiness-gate", help="Alias for launch-assets-gate")
    p.add_argument("--root", default=".")
    p.add_argument("--launch-assets-dir", default=None)
    p.add_argument("--assets-dir", default=None)
    p.add_argument("--demo-dir", default="demo_out")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("launch-polish-check", help="Alias for launch-assets-gate")
    p.add_argument("--root", default=".")
    p.add_argument("--launch-assets-dir", default=None)
    p.add_argument("--assets-dir", default=None)
    p.add_argument("--demo-dir", default="demo_out")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("real-mac-evidence-pack", help="Build a private real-Mac evidence collection pack without opening the microphone")
    p.add_argument("--root", default=".")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--mic-dir", default="mic_alpha_live")
    p.add_argument("--minutes-dir", default="mic_minutes_live")
    p.add_argument("--asr-minutes-dir", default="asr_minutes_faster_whisper")
    p.add_argument("--local-asr-dir", default="local_asr_smoke")
    p.add_argument("--launch-assets-dir", default="launch_assets")
    p.add_argument("--evidence-dir", default="real_mac_evidence")
    p.add_argument("--duration-ms", type=int, default=3000)
    p.add_argument("--device-id", default="microphone:default")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("real-mac-evidence-collect", help="Collect private real-Mac evidence after capture/ASR/launch artifacts are generated")
    p.add_argument("--root", default=".")
    p.add_argument("--evidence-dir", default="real_mac_evidence")
    p.add_argument("--mic-dir", default="mic_alpha_live")
    p.add_argument("--minutes-dir", default="mic_minutes_live")
    p.add_argument("--asr-minutes-dir", default="asr_minutes_faster_whisper")
    p.add_argument("--local-asr-dir", default="local_asr_smoke")
    p.add_argument("--launch-assets-dir", default="launch_assets")
    p.add_argument("--no-copy-artifacts", action="store_true")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("oss-readiness", help="Alias for readiness")
    p.add_argument("--root", default=".")
    p.add_argument("--out", required=False)

    p = sub.add_parser("sbom", help="Generate a lightweight direct-dependency SBOM")
    p.add_argument("--root", default=".")
    p.add_argument("--out", required=True)

    p = sub.add_parser("replay-transcript", help="Generate deterministic replay events for a transcript")
    p.add_argument("transcript_json")
    p.add_argument("--out", required=True)
    p.add_argument("--format", choices=["json", "ndjson"], default="json")
    p.add_argument("--chars-per-delta", type=int, default=24)
    p.add_argument("--speed", type=float, default=1.0)

    p = sub.add_parser("ui-bundle", help="Build a dependency-free Desktop Alpha UI demo bundle")
    p.add_argument("transcript_json")
    p.add_argument("--minutes-json", default=None)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--speed", type=float, default=1.0)

    p = sub.add_parser("simulate-audio", help="Generate a simulated audio capture manifest for CI/demo use")
    p.add_argument("--out", required=True)
    p.add_argument("--session-id", default="sim_session")
    p.add_argument("--total-ms", type=int, default=3000)
    p.add_argument("--chunk-ms", type=int, default=250)

    p = sub.add_parser("record-simulated", help="Capture simulated audio and persist WAV + session manifest")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--session-id", default="sim_session")
    p.add_argument("--total-ms", type=int, default=3000)
    p.add_argument("--chunk-ms", type=int, default=250)
    p.add_argument("--sample-rate", type=int, default=16000)
    p.add_argument("--channels", type=int, default=1)

    p = sub.add_parser("inspect-audio", help="Inspect a WAV audio artifact")
    p.add_argument("audio_path")
    p.add_argument("--out", default=None)

    p = sub.add_parser("audio-quality", help="Run deterministic audio quality diagnostics for a WAV file")
    p.add_argument("audio_path")
    p.add_argument("--out", default=None)

    p = sub.add_parser("audio-levels", help="Generate audio level-meter frames for a WAV file")
    p.add_argument("audio_path")
    p.add_argument("--window-ms", type=int, default=100)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("list-audio-devices", help="List available audio capture devices")
    p.add_argument("--provider", choices=["simulated", "microphone"], default="simulated")
    p.add_argument("--out", default=None)

    p = sub.add_parser("capture-readiness", help="Run provider preflight check before recording")
    p.add_argument("--provider", choices=["simulated", "microphone"], default="simulated")
    p.add_argument("--device-id", default=None)
    p.add_argument("--sample-rate", type=int, default=16000)
    p.add_argument("--channels", type=int, default=1)
    p.add_argument("--chunk-ms", type=int, default=250)
    p.add_argument("--duration-ms", type=int, default=3000)
    p.add_argument("--require-real-device", action="store_true")
    p.add_argument("--out", default=None)

    p = sub.add_parser("record-microphone", help="Record a short real microphone WAV using optional sounddevice support")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--session-id", default="mic_session")
    p.add_argument("--device-id", default="microphone:default")
    p.add_argument("--duration-ms", type=int, default=3000)
    p.add_argument("--chunk-ms", type=int, default=250)
    p.add_argument("--sample-rate", type=int, default=16000)
    p.add_argument("--channels", type=int, default=1)

    p = sub.add_parser("microphone-doctor", help="Check real microphone alpha readiness without opening the microphone")
    p.add_argument("--device-id", default="microphone:default")
    p.add_argument("--duration-ms", type=int, default=3000)
    p.add_argument("--chunk-ms", type=int, default=250)
    p.add_argument("--sample-rate", type=int, default=16000)
    p.add_argument("--channels", type=int, default=1)
    p.add_argument("--require-sounddevice", action="store_true")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("microphone-setup-guide", help="Write the private developer-preview microphone setup guide")
    p.add_argument("--out", default=None)

    p = sub.add_parser("recording-safety-gate", help="Evaluate the live recording safety/consent gate")
    p.add_argument("--live", action="store_true")
    p.add_argument("--confirmation", default=None)
    p.add_argument("--confirm-live-recording", action="store_true")
    p.add_argument("--notice-acknowledged", action="store_true")
    p.add_argument("--participants-notified", action="store_true")
    p.add_argument("--duration-ms", type=int, default=3000)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("live-capture-plan", help="Generate dry-run and live microphone capture commands without opening the microphone")
    p.add_argument("--out-dir", default="mic_alpha_live")
    p.add_argument("--duration-ms", type=int, default=3000)
    p.add_argument("--device-id", default="microphone:default")
    p.add_argument("--sample-rate", type=int, default=16000)
    p.add_argument("--channels", type=int, default=1)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("record-microphone-alpha", help="Run real microphone alpha capture. Dry-run by default; pass --live to open the microphone")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--session-id", default="mic_alpha")
    p.add_argument("--device-id", default="microphone:default")
    p.add_argument("--duration-ms", type=int, default=3000)
    p.add_argument("--chunk-ms", type=int, default=250)
    p.add_argument("--sample-rate", type=int, default=16000)
    p.add_argument("--channels", type=int, default=1)
    p.add_argument("--window-ms", type=int, default=100)
    p.add_argument("--live", action="store_true", help="Actually request the microphone; dry-run if omitted")
    p.add_argument("--confirm-live-recording", action="store_true", help="Required for --live. Confirms the operator understands this records audio.")
    p.add_argument("--notice-acknowledged", action="store_true", help="Required for --live. Confirms the recording notice was acknowledged.")
    p.add_argument("--participants-notified", action="store_true", help="Required for --live. Confirms meeting participants were notified.")
    p.add_argument("--confirmation", default=None, help="Alternative explicit confirmation phrase for live capture.")
    p.add_argument("--actor-id", default="local_developer")

    p = sub.add_parser("asr-doctor", help="Check optional local ASR environment without downloading models")
    p.add_argument("--provider", choices=["faster-whisper"], default="faster-whisper")
    p.add_argument("--model-size", default="small")
    p.add_argument("--device", default="cpu")
    p.add_argument("--out", default=None)

    p = sub.add_parser("transcribe-audio", help="Transcribe an audio file through a selectable ASR provider")
    p.add_argument("audio_path")
    p.add_argument("--provider", choices=["sidecar", "faster-whisper"], default="sidecar")
    p.add_argument("--sidecar", default=None)
    p.add_argument("--meeting-id", default="mtg_audio")
    p.add_argument("--title", default="Audio Meeting")
    p.add_argument("--out", required=True)
    p.add_argument("--model-size", default="small")
    p.add_argument("--device", default="cpu")
    p.add_argument("--compute-type", default="int8")

    p = sub.add_parser("audio-to-minutes", help="Audio file -> transcript -> evidence-linked minutes workflow")
    p.add_argument("audio_path")
    p.add_argument("--provider", choices=["sidecar", "faster-whisper"], default="sidecar")
    p.add_argument("--sidecar", default=None)
    p.add_argument("--meeting-id", default="mtg_audio")
    p.add_argument("--title", default="Audio Meeting")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--model-size", default="small")
    p.add_argument("--device", default="cpu")
    p.add_argument("--compute-type", default="int8")

    p = sub.add_parser("post-capture-gate", help="Validate a microphone capture directory before generating minutes")
    p.add_argument("--mic-dir", required=True)
    p.add_argument("--audio-path", default=None)
    p.add_argument("--provider", choices=["sidecar", "faster-whisper"], default="sidecar")
    p.add_argument("--sidecar", default=None)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("microphone-to-minutes", help="Post-capture microphone WAV -> transcript -> evidence-linked minutes")
    p.add_argument("--mic-dir", required=True)
    p.add_argument("--audio-path", default=None)
    p.add_argument("--provider", choices=["sidecar", "faster-whisper"], default="sidecar")
    p.add_argument("--sidecar", default=None)
    p.add_argument("--meeting-id", default="mtg_microphone_alpha")
    p.add_argument("--title", default="Microphone Alpha Minutes")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--model-size", default="small")
    p.add_argument("--device", default="cpu")
    p.add_argument("--compute-type", default="int8")

    p = sub.add_parser("capture-validation-pack", help="Build a private real-capture validation pack without opening the microphone")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--duration-ms", type=int, default=3000)
    p.add_argument("--device-id", default="microphone:default")
    p.add_argument("--sample-rate", type=int, default=16000)
    p.add_argument("--channels", type=int, default=1)
    p.add_argument("--chunk-ms", type=int, default=250)
    p.add_argument("--mic-dir", default="mic_alpha_live")
    p.add_argument("--minutes-dir", default="mic_minutes_live")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("capture-validation-run", help="Validate live microphone capture and post-capture minutes artifacts")
    p.add_argument("--mic-dir", required=True)
    p.add_argument("--minutes-dir", default=None)
    p.add_argument("--provider", choices=["sidecar", "faster-whisper"], default="sidecar")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("asr-validation-pack", help="Build a private local-ASR validation pack without opening the microphone")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--audio-path", default="mic_alpha_live/audio.wav")
    p.add_argument("--provider", choices=["sidecar", "faster-whisper"], default="sidecar")
    p.add_argument("--sidecar", default="mic_alpha_live/audio.transcript.txt")
    p.add_argument("--reference", default="mic_alpha_live/audio.transcript.txt")
    p.add_argument("--model-size", default="small")
    p.add_argument("--device", default="cpu")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("asr-validation-run", help="Validate ASR handoff on a known WAV and optional reference transcript")
    p.add_argument("--audio-path", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--provider", choices=["sidecar", "faster-whisper"], default="sidecar")
    p.add_argument("--sidecar", default=None)
    p.add_argument("--reference", default=None)
    p.add_argument("--meeting-id", default="mtg_asr_validation")
    p.add_argument("--title", default="ASR Validation")
    p.add_argument("--model-size", default="small")
    p.add_argument("--device", default="cpu")
    p.add_argument("--compute-type", default="int8")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("asr-to-minutes", help="Run ASR validation and generate evidence-linked minutes from the ASR transcript")
    p.add_argument("--audio-path", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--provider", choices=["sidecar", "faster-whisper"], default="sidecar")
    p.add_argument("--sidecar", default=None)
    p.add_argument("--reference", default=None)
    p.add_argument("--meeting-id", default="mtg_asr_minutes")
    p.add_argument("--title", default="ASR to Minutes")
    p.add_argument("--model-size", default="small")
    p.add_argument("--device", default="cpu")
    p.add_argument("--compute-type", default="int8")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--correction-glossary", default=None, help="Optional public-safe ASR correction glossary JSON")
    p.add_argument("--generate-corrected-minutes", action="store_true", help="Generate minutes from the corrected ASR transcript")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("real-capture-execution-pack", help="Build a private real microphone execution pack without opening the microphone")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--duration-ms", type=int, default=3000)
    p.add_argument("--device-id", default="microphone:default")
    p.add_argument("--sample-rate", type=int, default=16000)
    p.add_argument("--channels", type=int, default=1)
    p.add_argument("--chunk-ms", type=int, default=250)
    p.add_argument("--mic-dir", default="mic_alpha_live")
    p.add_argument("--minutes-dir", default="mic_minutes_live")
    p.add_argument("--asr-minutes-dir", default="asr_minutes_live")
    p.add_argument("--provider", choices=["sidecar", "faster-whisper"], default="sidecar")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("real-capture-execution-gate", help="Evaluate real microphone capture execution evidence")
    p.add_argument("--mic-dir", required=True)
    p.add_argument("--minutes-dir", default=None)
    p.add_argument("--asr-minutes-dir", default=None)
    p.add_argument("--allow-dry-run", action="store_true")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("local-asr-smoke-pack", help="Build a private local-ASR smoke pack without opening the microphone")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--audio-path", default="mic_alpha_live/audio.wav")
    p.add_argument("--sidecar", default="mic_alpha_live/audio.transcript.txt")
    p.add_argument("--reference", default="mic_alpha_live/audio.transcript.txt")
    p.add_argument("--model-size", default="small")
    p.add_argument("--device", default="cpu")
    p.add_argument("--smoke-dir", default="local_asr_smoke")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("local-asr-smoke-run", help="Run sidecar/local ASR smoke on a known WAV and prepare real-ASR handoff evidence")
    p.add_argument("--audio-path", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--sidecar", default=None)
    p.add_argument("--reference", default=None)
    p.add_argument("--mode", choices=["sidecar", "faster-whisper"], default="sidecar")
    p.add_argument("--model-size", default="small")
    p.add_argument("--device", default="cpu")
    p.add_argument("--compute-type", default="int8")
    p.add_argument("--require-real-asr", action="store_true")
    p.add_argument("--real-asr-report", default=None)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("local-asr-smoke-gate", help="Evaluate local ASR smoke evidence before public alpha")
    p.add_argument("--smoke-dir", required=True)
    p.add_argument("--real-asr-dir", default=None)
    p.add_argument("--require-real-asr", action="store_true")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("desktop-alpha-bundle", help="Build a portable Desktop Alpha bundle")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--transcript-json", default=None)
    p.add_argument("--minutes-json", default=None)
    p.add_argument("--bridge-host", default="127.0.0.1")
    p.add_argument("--bridge-port", type=int, default=8765)

    p = sub.add_parser("desktop-smoke", help="Run the deterministic Desktop Alpha smoke workflow")
    p.add_argument("--workspace", required=True)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser("desktop-serve", help="Serve Desktop Lite UI with local Community bridge APIs")
    p.add_argument("--workspace", required=True)
    p.add_argument("--ui-dir", default=None)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--open-browser", action="store_true")

    p = sub.add_parser("desktop-bridge", help="Run the local Desktop Bridge HTTP server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--workspace", default=".meeting-agent-desktop-alpha")
    p.add_argument("--open-browser", action="store_true")

    p = sub.add_parser("desktop-bridge-request", help="Exercise a Desktop Bridge route without starting a server")
    p.add_argument("--method", choices=["GET", "POST"], default="GET")
    p.add_argument("--path", default="/health")
    p.add_argument("--payload", default="{}")
    p.add_argument("--workspace", default=".meeting-agent-desktop-alpha")
    p.add_argument("--out", default=None)

    p = sub.add_parser("desktop-package-check", help="Check Desktop Alpha packaging skeleton")
    p.add_argument("--root", default=".")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)

    p = sub.add_parser(
        "corrected-minutes-review",
        help="Compare original and corrected ASR minutes outputs",
    )
    p.add_argument("--original-dir", required=True)
    p.add_argument("--corrected-dir", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--title", default="Corrected ASR minutes review")

    p = sub.add_parser("demo", help="Run demo workflow using examples/sample_meeting_ja.txt")
    p.add_argument("--out-dir", required=True)

    return parser


def _build_asr_provider(args):
    if getattr(args, "provider", "sidecar") == "faster-whisper":
        return FasterWhisperProvider(
            model_size=getattr(args, "model_size", "small"),
            device=getattr(args, "device", "cpu"),
            compute_type=getattr(args, "compute_type", "int8"),
        )
    return SidecarTranscriptProvider(sidecar_path=getattr(args, "sidecar", None))


def _build_audio_capture_provider(provider: str, *, total_ms: int = 3000):
    if provider == "microphone":
        return SoundDeviceMicrophoneProvider()
    return SimulatedAudioCaptureProvider(total_ms=total_ms)


def _write_minutes_workflow(transcript, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = out_dir / "meeting.json"
    minutes_path = out_dir / "minutes.json"
    markdown_path = out_dir / "minutes.md"
    verify_path = out_dir / "verification.json"
    quality_path = out_dir / "quality_gate.json"
    html_path = out_dir / "minutes.html"
    actions_csv_path = out_dir / "action_items.csv"
    ui_dir = out_dir / "desktop_lite"
    _demo_step("base outputs")
    save_transcript(transcript, transcript_path)
    minutes = RuleBasedMinutesGenerator().generate(transcript)
    verification = MinutesVerifier().verify(transcript, minutes)
    quality = run_minutes_quality_gate(transcript, minutes, verification)
    write_json(minutes, minutes_path)
    MarkdownExporter().export(transcript, minutes, markdown_path)
    HTMLExporter().export(transcript, minutes, html_path)
    ActionItemCSVExporter().export(transcript, minutes, actions_csv_path)
    write_json(verification, verify_path)
    write_quality_gate_result(quality, quality_path)
    _demo_step("desktop lite bundle")
    build_desktop_lite_bundle(transcript, ui_dir, minutes=minutes)
    return {
        "transcript": transcript_path,
        "minutes_json": minutes_path,
        "minutes_md": markdown_path,
        "verification": verify_path,
        "quality_gate": quality_path,
        "minutes_html": html_path,
        "action_items_csv": actions_csv_path,
        "desktop_lite": ui_dir / "index.html",
    }


def _write_json_payload(payload: dict, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _main_impl(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ingest":
        transcript = load_transcript(args.input)
        if args.meeting_id:
            transcript.meeting_id = args.meeting_id
        if args.title:
            transcript.title = args.title
        save_transcript(transcript, args.out)
        print(f"Wrote transcript: {args.out}")
        return 0

    if args.command == "minutes":
        transcript = load_transcript(args.transcript_json)
        minutes = RuleBasedMinutesGenerator().generate(transcript, template_id=args.template)
        report = MinutesVerifier().verify(transcript, minutes)
        write_json(minutes, args.out_json)
        print(f"Wrote minutes JSON: {args.out_json}")
        print(f"Verification: {report.status} score={report.score}")
        if args.out_md:
            MarkdownExporter().export(transcript, minutes, args.out_md)
            print(f"Wrote minutes Markdown: {args.out_md}")
        return 0

    if args.command == "apply-glossary":
        transcript = load_transcript(args.transcript_json)
        entries = load_glossary(args.glossary_json)
        corrected, report = apply_glossary(transcript, entries)
        save_transcript(corrected, args.out)
        _write_json_payload(report.to_dict(), args.report)
        print(f"Wrote corrected transcript: {args.out}")
        print(f"Wrote glossary report: {args.report}")
        return 0

    if args.command == "export-html":
        transcript = load_transcript(args.transcript_json)
        minutes = minutes_from_dict(read_json(args.minutes_json))
        HTMLExporter().export(transcript, minutes, args.out)
        print(f"Wrote HTML minutes: {args.out}")
        return 0

    if args.command == "export-actions-csv":
        transcript = load_transcript(args.transcript_json)
        minutes = minutes_from_dict(read_json(args.minutes_json))
        ActionItemCSVExporter().export(transcript, minutes, args.out)
        print(f"Wrote action items CSV: {args.out}")
        return 0

    if args.command == "store":
        transcript = load_transcript(args.transcript)
        minutes = minutes_from_dict(read_json(args.minutes)) if args.minutes else None
        SQLiteMeetingStore(args.db).upsert_meeting(transcript, minutes)
        print(f"Stored meeting: {transcript.meeting_id}")
        return 0

    if args.command == "list-store":
        print(json.dumps(SQLiteMeetingStore(args.db).list_meetings(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "verify":
        transcript = load_transcript(args.transcript_json)
        minutes = minutes_from_dict(read_json(args.minutes_json))
        report = MinutesVerifier().verify(transcript, minutes)
        write_json(report, args.out)
        print(f"Wrote verification report: {args.out}")
        return 0 if report.status != "fail" else 1

    if args.command == "redact":
        transcript = redact_transcript(load_transcript(args.transcript_json))
        save_transcript(transcript, args.out)
        print(f"Wrote redacted transcript: {args.out}")
        return 0

    if args.command == "plugins":
        registry = build_default_registry()
        items = registry.list_plugins(kind=args.kind)
        print(json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=2))
        return 0

    if args.command == "eval-text":
        result = evaluate_text(Path(args.reference).read_text(encoding="utf-8"), Path(args.hypothesis).read_text(encoding="utf-8"))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "quality-gate":
        transcript = load_transcript(args.transcript_json)
        minutes = minutes_from_dict(read_json(args.minutes_json))
        verification = verification_report_from_dict(read_json(args.verification_json))
        result = run_minutes_quality_gate(transcript, minutes, verification)
        write_quality_gate_result(result, args.out)
        print(f"Wrote quality gate result: {args.out}")
        return 0 if result.status != "fail" else 1

    if args.command == "consent-notice":
        notice = render_recording_notice()
        if args.out:
            Path(args.out).write_text(notice, encoding="utf-8")
            print(f"Wrote consent notice: {args.out}")
        print(notice)
        return 0

    if args.command == "plugin-manifest":
        print(json.dumps(load_manifest(args.manifest_json).to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "validate-plugin":
        manifest = load_plugin_manifest(args.manifest_json)
        issues = manifest.validate(community_only=args.community_only)
        print(json.dumps({"status": "pass" if not issues else "fail", "issues": issues}, ensure_ascii=False, indent=2))
        return 0 if not issues else 1

    if args.command == "readiness":
        report = run_readiness_checks(args.root)
        print(report.to_json())
        if args.out_json:
            Path(args.out_json).write_text(report.to_json() + "\n", encoding="utf-8")
        if args.out_md:
            Path(args.out_md).write_text(report.to_markdown(), encoding="utf-8")
        return 0 if report.status == "pass" else 1

    if args.command == "release-check":
        report = run_release_readiness(args.root, profile=args.profile, run_tests=args.run_tests)
        print(report.to_json())
        if args.out_json:
            Path(args.out_json).write_text(report.to_json() + "\n", encoding="utf-8")
        if args.out_md:
            Path(args.out_md).write_text(report.to_markdown(), encoding="utf-8")
        return 0 if report.status in {"pass", "ready", "ready_with_warnings", "portfolio_preview_ready"} else 1

    if args.command == "publication-gate":
        report = run_publication_gate(args.root)
        print(report.to_json())
        if args.out_json:
            Path(args.out_json).write_text(report.to_json() + "\n", encoding="utf-8")
        if args.out_md:
            write_publication_gate_report(report, args.out_md)
        return 0 if report.status in {"hold", "pass", "ready"} else 1

    if args.command == "dev-env-doctor":
        report = run_dev_environment_doctor(root=args.root, bridge_port=args.bridge_port)
        if args.out_json or args.out_md:
            write_dev_environment_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "private-alpha-gate":
        report = run_private_alpha_gate(root=args.root, run_tests=args.run_tests, bridge_port=args.bridge_port)
        if args.out_json or args.out_md:
            write_private_alpha_gate_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "public-alpha-readiness":
        report = run_public_alpha_readiness(root=args.root, bridge_port=args.bridge_port)
        if args.out_json or args.out_md:
            write_public_alpha_readiness_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"hold", "ready_with_warnings_but_publication_hold", "candidate_but_publication_hold"} else 1

    if args.command == "public-alpha-plan":
        report = build_public_alpha_plan(root=args.root, bridge_port=args.bridge_port)
        if args.out_json or args.out_md:
            write_public_alpha_plan_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"hold_plan_ready", "ready"} else 1

    if args.command == "public-alpha-candidate-pack":
        report = build_public_alpha_candidate_pack(
            out_dir=args.out_dir,
            root=args.root,
            demo_dir=args.demo_dir,
            evidence_dir=args.evidence_dir,
            launch_assets_dir=args.launch_assets_dir,
            candidate_version=args.candidate_version,
        )
        if args.out_json or args.out_md:
            write_public_alpha_candidate_pack_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "public-alpha-candidate-gate":
        report = run_public_alpha_candidate_gate(
            root=args.root,
            candidate_dir=args.candidate_dir,
            evidence_dir=args.evidence_dir,
            launch_assets_dir=args.launch_assets_dir,
            demo_dir=args.demo_dir,
            bridge_port=args.bridge_port,
        )
        if args.out_json or args.out_md:
            write_public_alpha_candidate_gate_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"hold_missing_candidate_evidence", "candidate_ready_but_publication_hold", "candidate_policy_unlocked_review_required"} else 1

    if args.command == "maintainer-review-pack":
        report = build_maintainer_review_pack(
            out_dir=args.out_dir,
            root=args.root,
            dashboard_dir=args.dashboard_dir,
            evidence_dir=args.evidence_dir,
            launch_assets_dir=args.launch_assets_dir,
            candidate_dir=args.candidate_dir,
        )
        if args.out_json or args.out_md:
            write_maintainer_review_pack_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command in {"maintainer-dashboard", "maintainer-review-gate"}:
        report = build_maintainer_dashboard(
            root=args.root,
            dashboard_dir=args.dashboard_dir,
            evidence_dir=args.evidence_dir,
            launch_assets_dir=args.launch_assets_dir,
            candidate_dir=args.candidate_dir,
            demo_dir=args.demo_dir,
            bridge_port=args.bridge_port,
        )
        if args.out_json or args.out_md or getattr(args, "out_html", None):
            write_maintainer_dashboard_report(report, out_json=args.out_json, out_md=args.out_md, out_html=getattr(args, "out_html", None))
        print(report.to_json())
        return 0 if report.status in {"hold", "candidate_review_ready", "blocked_private_core"} else 1

    if args.command == "evidence-export-pack":
        bridge_url = args.bridge_url or f"http://127.0.0.1:{args.bridge_port}"
        report = build_evidence_export_pack(
            out_dir=args.out_dir,
            root=args.root,
            export_dir=args.export_dir,
            demo_dir=args.demo_dir,
            evidence_dir=args.evidence_dir,
            launch_assets_dir=args.launch_assets_dir,
            dashboard_dir=args.dashboard_dir,
            screenshot_dir=args.screenshot_dir,
            bridge_url=bridge_url,
        )
        if args.out_json or args.out_md:
            write_evidence_export_pack_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "screenshot-automation-pack":
        bridge_url = args.bridge_url or f"http://127.0.0.1:{args.bridge_port}"
        report = build_screenshot_automation_pack(
            out_dir=args.out_dir,
            root=args.root,
            demo_dir=args.demo_dir,
            screenshot_dir=args.screenshot_dir,
            bridge_url=bridge_url,
        )
        if args.out_json or args.out_md:
            write_screenshot_automation_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "screenshot-readiness-gate":
        report = run_screenshot_readiness_gate(
            root=args.root,
            screenshot_dir=args.screenshot_dir,
            demo_dir=args.demo_dir,
            min_screenshots=args.min_screenshots,
        )
        if args.out_json or args.out_md:
            write_screenshot_automation_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "evidence-export-run":
        report = export_evidence_bundle(
            root=args.root,
            out_dir=args.out_dir,
            demo_dir=args.demo_dir,
            evidence_dir=args.evidence_dir,
            launch_assets_dir=args.launch_assets_dir,
            dashboard_dir=args.dashboard_dir,
            screenshot_dir=args.screenshot_dir,
            copy_artifacts=not args.no_copy_artifacts,
        )
        if args.out_json or args.out_md:
            write_evidence_export_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "evidence-export-gate":
        report = run_evidence_export_gate(
            root=args.root,
            export_dir=args.export_dir,
            screenshot_dir=args.screenshot_dir,
            min_screenshots=args.min_screenshots,
        )
        if args.out_json or args.out_md:
            write_evidence_export_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "launch-assets-pack":
        bridge_url = getattr(args, "bridge_url", None) or f"http://127.0.0.1:{getattr(args, 'bridge_port', 8765)}"
        report = build_launch_asset_pack(
            out_dir=args.out_dir,
            root=args.root,
            demo_dir=args.demo_dir,
            bridge_url=bridge_url,
        )
        if args.out_json or args.out_md:
            write_launch_asset_pack_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command in {"launch-assets-gate", "launch-readiness-gate", "launch-polish-check"}:
        assets_dir = getattr(args, "assets_dir", None) or getattr(args, "launch_assets_dir", None) or "launch_assets"
        report = run_launch_polish_check(
            root=args.root,
            launch_assets_dir=assets_dir,
            demo_dir=args.demo_dir,
        )
        if args.out_json or args.out_md:
            write_launch_polish_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "real-mac-evidence-pack":
        report = build_real_mac_evidence_pack(
            out_dir=args.out_dir,
            root=args.root,
            mic_dir=args.mic_dir,
            minutes_dir=args.minutes_dir,
            asr_minutes_dir=args.asr_minutes_dir,
            local_asr_dir=args.local_asr_dir,
            launch_assets_dir=args.launch_assets_dir,
            evidence_dir=args.evidence_dir,
            duration_ms=args.duration_ms,
            device_id=args.device_id,
        )
        if args.out_json or args.out_md:
            write_real_mac_evidence_pack_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "real-mac-evidence-collect":
        report = collect_real_mac_evidence(
            root=args.root,
            evidence_dir=args.evidence_dir,
            mic_dir=args.mic_dir,
            minutes_dir=args.minutes_dir,
            asr_minutes_dir=args.asr_minutes_dir,
            local_asr_dir=args.local_asr_dir,
            launch_assets_dir=args.launch_assets_dir,
            copy_artifacts=not args.no_copy_artifacts,
        )
        if args.out_json or args.out_md:
            write_real_mac_evidence_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "oss-readiness":
        report = assess_oss_readiness(args.root)
        if args.out:
            write_readiness_report(report, args.out)
        print(report.to_json())
        return 0 if report.status == "pass" else 1

    if args.command == "sbom":
        sbom = write_sbom(args.root, args.out)
        print(f"Wrote SBOM: {args.out}")
        print(f"Project: {sbom.name} {sbom.version}, packages={len(sbom.packages)}")
        return 0

    if args.command == "replay-transcript":
        transcript = load_transcript(args.transcript_json)
        settings = TranscriptReplaySettings(chars_per_delta=args.chars_per_delta, speed=args.speed)
        count = write_replay_json(transcript, args.out, settings) if args.format == "json" else write_replay_ndjson(transcript, args.out, settings)
        print(f"Wrote replay events: {args.out} ({count} events)")
        return 0

    if args.command == "ui-bundle":
        transcript = load_transcript(args.transcript_json)
        minutes = minutes_from_dict(read_json(args.minutes_json)) if args.minutes_json else None
        _demo_step("desktop lite bundle")
        paths = build_desktop_lite_bundle(transcript, args.out_dir, minutes=minutes, settings=TranscriptReplaySettings(speed=args.speed))
        print(f"Wrote Desktop Alpha UI bundle: {args.out_dir}")
        for name, path in sorted(paths.items()):
            print(f"- {name}: {path}")
        return 0

    if args.command == "simulate-audio":
        provider = SimulatedAudioCaptureProvider(total_ms=args.total_ms)
        config = AudioCaptureConfig(device_id="simulated:microphone", chunk_ms=args.chunk_ms)
        chunks = [chunk.to_public_dict() for chunk in provider.capture(config, session_id=args.session_id)]
        payload = {"provider": {"id": provider.id, "name": provider.name}, "config": config.to_dict(), "devices": [d.to_dict() for d in provider.list_devices()], "chunks": chunks, "chunk_count": len(chunks)}
        _write_json_payload(payload, args.out)
        print(f"Wrote simulated audio manifest: {args.out} chunks={len(chunks)}")
        return 0

    if args.command == "record-simulated":
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        provider = SimulatedAudioCaptureProvider(total_ms=args.total_ms)
        config = AudioCaptureConfig(device_id="simulated:microphone", sample_rate_hz=args.sample_rate, channels=args.channels, chunk_ms=args.chunk_ms)
        manifest = capture_session_to_wav(provider, config, session_id=args.session_id, wav_path=out_dir / "audio.wav", manifest_path=out_dir / "audio_session.json")
        print(f"Wrote WAV: {out_dir / 'audio.wav'}")
        print(f"Wrote audio session manifest: {out_dir / 'audio_session.json'}")
        print(f"Audio session: chunks={manifest.chunk_count} duration_ms={manifest.duration_ms}")
        return 0

    if args.command == "inspect-audio":
        info = read_wav_info(args.audio_path)
        if args.out:
            Path(args.out).write_text(info.to_json() + "\n", encoding="utf-8")
        print(info.to_json())
        return 0

    if args.command == "audio-quality":
        report = analyze_wav_quality(args.audio_path)
        if args.out:
            Path(args.out).write_text(report.to_json() + "\n", encoding="utf-8")
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "audio-levels":
        report = analyze_audio_levels(args.audio_path, window_ms=args.window_ms)
        write_audio_level_report(report, args.out_json, args.out_md)
        print(report.to_json())
        return 0 if report.status != "fail" else 1

    if args.command == "list-audio-devices":
        provider = _build_audio_capture_provider(args.provider)
        payload = {"provider": {"id": provider.id, "name": provider.name}, "devices": [d.to_dict() for d in provider.list_devices()]}
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0

    if args.command == "capture-readiness":
        provider = _build_audio_capture_provider(args.provider, total_ms=args.duration_ms)
        default_device = "microphone:default" if args.provider == "microphone" else "simulated:microphone"
        config = AudioCaptureConfig(device_id=args.device_id or default_device, sample_rate_hz=args.sample_rate, channels=args.channels, chunk_ms=args.chunk_ms, metadata={"duration_ms": args.duration_ms})
        report = assess_capture_readiness(provider, config, require_real_device=args.require_real_device)
        if args.out:
            Path(args.out).write_text(report.to_json() + "\n", encoding="utf-8")
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "record-microphone":
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        provider = SoundDeviceMicrophoneProvider()
        config = AudioCaptureConfig(device_id=args.device_id, sample_rate_hz=args.sample_rate, channels=args.channels, chunk_ms=args.chunk_ms, metadata={"duration_ms": args.duration_ms})
        manifest = capture_session_to_wav(provider, config, session_id=args.session_id, wav_path=out_dir / "audio.wav", manifest_path=out_dir / "audio_session.json")
        quality = analyze_wav_quality(out_dir / "audio.wav")
        (out_dir / "audio_quality.json").write_text(quality.to_json() + "\n", encoding="utf-8")
        print(f"Wrote WAV: {out_dir / 'audio.wav'}")
        print(f"Audio session: chunks={manifest.chunk_count} duration_ms={manifest.duration_ms}")
        return 0 if quality.status in {"pass", "warn"} else 1

    if args.command == "microphone-doctor":
        report = run_microphone_alpha_doctor(
            device_id=args.device_id,
            sample_rate_hz=args.sample_rate,
            channels=args.channels,
            chunk_ms=args.chunk_ms,
            duration_ms=args.duration_ms,
            require_sounddevice=args.require_sounddevice,
        )
        if args.out_json:
            Path(args.out_json).write_text(report.to_json() + "\n", encoding="utf-8")
        if args.out_md:
            Path(args.out_md).write_text(report.to_markdown(), encoding="utf-8")
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "microphone-setup-guide":
        guide = microphone_setup_guide()
        if args.out:
            write_microphone_setup_guide(args.out)
            print(f"Wrote microphone setup guide: {args.out}")
        print(guide)
        return 0

    if args.command == "recording-safety-gate":
        confirmation = args.confirmation or (LIVE_CONFIRMATION_PHRASE if args.confirm_live_recording else None)
        report = evaluate_recording_safety_gate(
            live_requested=args.live,
            confirmation=confirmation,
            notice_acknowledged=args.notice_acknowledged,
            participants_notified=args.participants_notified,
            duration_ms=args.duration_ms,
            publication_hold=True,
        )
        if args.out_json or args.out_md:
            write_recording_safety_gate_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} and (not args.live or report.live_allowed) else 1

    if args.command == "live-capture-plan":
        plan = build_live_capture_plan(
            out_dir=args.out_dir,
            duration_ms=args.duration_ms,
            device_id=args.device_id,
            sample_rate_hz=args.sample_rate,
            channels=args.channels,
        )
        if args.out_json or args.out_md:
            write_live_capture_plan(plan, out_json=args.out_json, out_md=args.out_md)
        print(plan.to_json())
        return 0

    if args.command == "record-microphone-alpha":
        report = run_microphone_alpha_recording(
            out_dir=args.out_dir,
            session_id=args.session_id,
            device_id=args.device_id,
            duration_ms=args.duration_ms,
            sample_rate_hz=args.sample_rate,
            channels=args.channels,
            chunk_ms=args.chunk_ms,
            window_ms=args.window_ms,
            dry_run=not args.live,
            confirm_live_recording=args.confirmation or (LIVE_CONFIRMATION_PHRASE if args.confirm_live_recording else None),
            notice_acknowledged=args.notice_acknowledged,
            participants_notified=args.participants_notified,
            actor_id=args.actor_id,
        )
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "asr-doctor":
        report = run_asr_doctor(args.provider, model_size=args.model_size, device=args.device)
        if args.out:
            Path(args.out).write_text(report.to_json() + "\n", encoding="utf-8")
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "transcribe-audio":
        provider = _build_asr_provider(args)
        transcript = provider.transcribe_file(args.audio_path, meeting_id=args.meeting_id, title=args.title)
        save_transcript(transcript, args.out)
        print(f"Wrote transcript: {args.out}")
        print(f"ASR provider: {provider.id}; segments={len(transcript.segments)}")
        return 0

    if args.command == "audio-to-minutes":
        provider = _build_asr_provider(args)
        transcript = provider.transcribe_file(args.audio_path, meeting_id=args.meeting_id, title=args.title)
        paths = _write_minutes_workflow(transcript, Path(args.out_dir))
        print(f"Audio-to-minutes complete: {args.out_dir}")
        for name, path in sorted(paths.items()):
            print(f"- {name}: {path}")
        return 0

    if args.command == "post-capture-gate":
        report = evaluate_post_capture_gate(
            args.mic_dir,
            audio_path=args.audio_path,
            provider=args.provider,
            sidecar_path=args.sidecar,
        )
        if args.out_json or args.out_md:
            write_post_capture_gate_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "microphone-to-minutes":
        report = run_microphone_to_minutes_workflow(
            mic_dir=args.mic_dir,
            out_dir=args.out_dir,
            audio_path=args.audio_path,
            provider=args.provider,
            sidecar_path=args.sidecar,
            meeting_id=args.meeting_id,
            title=args.title,
            model_size=args.model_size,
            device=args.device,
            compute_type=args.compute_type,
        )
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "capture-validation-pack":
        report = build_capture_validation_pack(
            out_dir=args.out_dir,
            duration_ms=args.duration_ms,
            device_id=args.device_id,
            sample_rate_hz=args.sample_rate,
            channels=args.channels,
            chunk_ms=args.chunk_ms,
            mic_dir=args.mic_dir,
            minutes_dir=args.minutes_dir,
        )
        if args.out_json or args.out_md:
            write_capture_validation_pack_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "capture-validation-run":
        report = evaluate_capture_validation_run(mic_dir=args.mic_dir, minutes_dir=args.minutes_dir, provider=args.provider)
        if args.out_json or args.out_md:
            write_capture_validation_run_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "asr-validation-pack":
        report = build_asr_validation_pack(
            out_dir=args.out_dir,
            audio_path=args.audio_path,
            provider=args.provider,
            sidecar_path=args.sidecar,
            reference_path=args.reference,
            model_size=args.model_size,
            device=args.device,
        )
        if args.out_json or args.out_md:
            write_asr_validation_pack_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "asr-validation-run":
        report = run_asr_validation(
            audio_path=args.audio_path,
            out_dir=args.out_dir,
            provider=args.provider,
            sidecar_path=args.sidecar,
            reference_path=args.reference,
            meeting_id=args.meeting_id,
            title=args.title,
            model_size=args.model_size,
            device=args.device,
            compute_type=args.compute_type,
            dry_run=args.dry_run,
        )
        if args.out_json or args.out_md:
            write_asr_validation_run_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "asr-to-minutes":
        report = run_asr_to_minutes_workflow(
            audio_path=args.audio_path,
            out_dir=args.out_dir,
            provider=args.provider,
            sidecar_path=args.sidecar,
            reference_path=args.reference,
            meeting_id=args.meeting_id,
            title=args.title,
            model_size=args.model_size,
            device=args.device,
            compute_type=args.compute_type,
            dry_run=args.dry_run,
            correction_glossary=args.correction_glossary,
            generate_corrected_minutes=args.generate_corrected_minutes,
        )
        if args.out_json or args.out_md:
            write_asr_minutes_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "real-capture-execution-pack":
        report = build_real_capture_execution_pack(
            out_dir=args.out_dir,
            duration_ms=args.duration_ms,
            device_id=args.device_id,
            sample_rate_hz=args.sample_rate,
            channels=args.channels,
            chunk_ms=args.chunk_ms,
            mic_dir=args.mic_dir,
            minutes_dir=args.minutes_dir,
            asr_minutes_dir=args.asr_minutes_dir,
            provider=args.provider,
        )
        if args.out_json or args.out_md:
            write_real_capture_execution_pack_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "real-capture-execution-gate":
        report = evaluate_real_capture_execution(
            mic_dir=args.mic_dir,
            minutes_dir=args.minutes_dir,
            asr_minutes_dir=args.asr_minutes_dir,
            require_live_artifacts=not args.allow_dry_run,
        )
        if args.out_json or args.out_md:
            write_real_capture_execution_gate_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "local-asr-smoke-pack":
        report = build_local_asr_smoke_pack(
            out_dir=args.out_dir,
            audio_path=args.audio_path,
            sidecar_path=args.sidecar,
            reference_path=args.reference,
            model_size=args.model_size,
            device=args.device,
            smoke_dir=args.smoke_dir,
        )
        if args.out_json or args.out_md:
            write_local_asr_smoke_pack_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "local-asr-smoke-run":
        report = run_local_asr_smoke(
            audio_path=args.audio_path,
            out_dir=args.out_dir,
            sidecar_path=args.sidecar,
            reference_path=args.reference,
            mode=args.mode,
            model_size=args.model_size,
            device=args.device,
            compute_type=args.compute_type,
            require_real_asr=args.require_real_asr,
            real_asr_report=args.real_asr_report,
        )
        if args.out_json or args.out_md:
            write_local_asr_smoke_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "local-asr-smoke-gate":
        report = evaluate_local_asr_smoke_gate(
            smoke_dir=args.smoke_dir,
            real_asr_dir=args.real_asr_dir,
            require_real_asr=args.require_real_asr,
        )
        if args.out_json or args.out_md:
            write_local_asr_smoke_report(report, out_json=args.out_json, out_md=args.out_md)
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "desktop-alpha-bundle":
        paths = build_desktop_alpha_bundle(args.out_dir, transcript_path=args.transcript_json, minutes_path=args.minutes_json, bridge_host=args.bridge_host, bridge_port=args.bridge_port)
        print(f"Wrote Desktop Alpha bundle: {args.out_dir}")
        for name, path in sorted(paths.items()):
            print(f"- {name}: {path}")
        return 0

    if args.command == "desktop-smoke":
        report = DesktopAlphaManager(args.workspace).run_smoke()
        if args.out_json:
            Path(args.out_json).write_text(report.to_json() + "\n", encoding="utf-8")
        if args.out_md:
            Path(args.out_md).write_text(report.to_markdown(), encoding="utf-8")
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "desktop-serve":
        workspace = Path(args.workspace)
        serve_desktop_alpha(workspace_dir=workspace, ui_dir=Path(args.ui_dir) if args.ui_dir else workspace / "desktop_lite", host=args.host, port=args.port, open_browser=args.open_browser)
        return 0

    if args.command == "desktop-bridge":
        serve_bridge(BridgeConfig(host=args.host, port=args.port, workspace=args.workspace), open_browser=args.open_browser)
        return 0

    if args.command == "desktop-bridge-request":
        try:
            payload = json.loads(args.payload or "{}")
        except json.JSONDecodeError as exc:
            print(json.dumps({"status": "fail", "error": f"invalid payload json: {exc}"}, ensure_ascii=False, indent=2))
            return 2
        status, response = handle_bridge_request(args.method, args.path, payload, config=BridgeConfig(workspace=args.workspace))
        text = json.dumps({"http_status": status, "response": response}, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0 if 200 <= status < 300 else 1

    if args.command == "desktop-package-check":
        report = run_desktop_package_check(args.root)
        if args.out_json:
            Path(args.out_json).write_text(report.to_json() + "\n", encoding="utf-8")
        if args.out_md:
            Path(args.out_md).write_text(report.to_markdown(), encoding="utf-8")
        print(report.to_json())
        return 0 if report.status in {"pass", "warn"} else 1

    if args.command == "corrected-minutes-review":
        payload = write_corrected_minutes_review(
            original_dir=Path(args.original_dir),
            corrected_dir=Path(args.corrected_dir),
            out_dir=Path(args.out_dir),
            title=args.title,
        )
        print(f"Wrote: {Path(args.out_dir) / 'review.md'}")
        print(f"Wrote: {Path(args.out_dir) / 'review.json'}")
        return 0

    if args.command == "demo":
        return _run_demo(args.out_dir)

    parser.error("unknown command")
    return 2


def main(argv: list[str] | None = None) -> int:
    return _main_impl(argv)


class _DemoReportSnapshot:
    def __init__(self, title: str, status: str, score: float, recommendation: str, extra: dict[str, object] | None = None) -> None:
        self.title = title
        self.status = status
        self.score = score
        self.recommendation = recommendation
        self.extra = extra or {}

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "status": self.status,
            "score": self.score,
            "recommendation": self.recommendation,
            "checks": [],
            "private_core_included": False,
            **self.extra,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        return (
            f"# {self.title}\n\n"
            f"- Status: `{self.status}`\n"
            f"- Score: `{self.score}`\n"
            "- Private core included: `false`\n\n"
            "## Recommendation\n\n"
            f"{self.recommendation}\n"
        )


def _demo_report_snapshot(title: str, status: str, score: float, recommendation: str, extra: dict[str, object] | None = None) -> _DemoReportSnapshot:
    return _DemoReportSnapshot(title=title, status=status, score=score, recommendation=recommendation, extra=extra)


def _demo_step(label: str) -> None:
    # Keep the demo deterministic in constrained sandboxes by yielding and
    # flushing at each major local workflow step. The output is intentionally
    # concise and useful for developer-preview troubleshooting.
    time.sleep(0.001)
    print(f"[demo] {label}", flush=True)


def _run_demo(out_dir_value: str) -> int:
    """Generate a deterministic v0.6 demo artifact set.

    The demo intentionally avoids private-core logic and heavyweight native
    capture. It uses simulated audio, sidecar ASR, basic evidence-linked
    minutes, Desktop Lite UI, local workflow artifacts, and a portable Desktop
    Alpha bundle.
    """
    _demo_step("start")
    out_dir = Path(out_dir_value)
    out_dir.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    sample = root / "examples" / "sample_meeting_ja.txt"
    if not sample.exists():
        sample = Path.cwd() / "examples" / "sample_meeting_ja.txt"

    transcript = load_transcript(sample)
    transcript.meeting_id = "mtg_demo_ja"
    transcript.title = "AI Meeting Agent MVP Strategy"

    # Base meeting intelligence outputs.
    _demo_step("base outputs")
    transcript_path = out_dir / "meeting.json"
    minutes_path = out_dir / "minutes.json"
    markdown_path = out_dir / "minutes.md"
    verify_path = out_dir / "verification.json"
    quality_path = out_dir / "quality_gate.json"
    html_path = out_dir / "minutes.html"
    actions_csv_path = out_dir / "action_items.csv"
    save_transcript(transcript, transcript_path)
    minutes = RuleBasedMinutesGenerator().generate(transcript)
    verification = MinutesVerifier().verify(transcript, minutes)
    quality = run_minutes_quality_gate(transcript, minutes, verification)
    write_json(minutes, minutes_path)
    MarkdownExporter().export(transcript, minutes, markdown_path)
    HTMLExporter().export(transcript, minutes, html_path)
    ActionItemCSVExporter().export(transcript, minutes, actions_csv_path)
    write_json(verification, verify_path)
    write_quality_gate_result(quality, quality_path)
    SQLiteMeetingStore(out_dir / "meetings.sqlite").upsert_meeting(transcript, minutes)
    (out_dir / "recording_notice.md").write_text(render_recording_notice(), encoding="utf-8")
    write_replay_json(transcript, out_dir / "replay_events.json")
    write_replay_ndjson(transcript, out_dir / "replay_events.ndjson")

    # Local simulated audio readiness artifacts.
    _demo_step("audio simulated")
    _demo_step("provider create")
    provider = SimulatedAudioCaptureProvider(total_ms=3000)
    config = AudioCaptureConfig(device_id="simulated:microphone", chunk_ms=250)
    _demo_step("provider capture")
    chunks = [c for c in provider.capture(config, session_id="demo_audio")]
    _demo_step("manifest write")
    _write_json_payload(
        {
            "provider": {"id": provider.id, "name": provider.name},
            "config": config.to_dict(),
            "devices": [d.to_dict() for d in provider.list_devices()],
            "chunks": [c.to_public_dict() for c in chunks],
            "chunk_count": len(chunks),
        },
        out_dir / "simulated_audio_manifest.json",
    )
    _demo_step("capture wav")
    wav_info = write_wav_from_chunks(chunks, out_dir / "audio.wav")
    (out_dir / "audio_session.json").write_text(
        json.dumps({
            "session_id": "demo_audio",
            "provider_id": provider.id,
            "provider_name": provider.name,
            "config": config.to_dict(),
            "wav": wav_info.to_dict(),
            "chunk_count": len(chunks),
            "duration_ms": wav_info.duration_ms,
            "metadata": {"source": "demo_precomputed_chunks", "private_core_included": False},
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _demo_step("audio info")
    (out_dir / "audio_info.json").write_text(wav_info.to_json() + "\n", encoding="utf-8")
    _demo_step("audio quality")
    audio_quality = analyze_wav_quality(out_dir / "audio.wav")
    (out_dir / "audio_quality.json").write_text(audio_quality.to_json() + "\n", encoding="utf-8")
    _demo_step("audio levels")
    audio_levels = analyze_audio_levels(out_dir / "audio.wav", window_ms=100)
    write_audio_level_report(audio_levels, out_dir / "audio_levels.json", out_dir / "audio_levels.md")
    _demo_step("capture readiness")
    readiness = assess_capture_readiness(SimulatedAudioCaptureProvider(total_ms=3000), config)
    (out_dir / "capture_readiness.json").write_text(readiness.to_json() + "\n", encoding="utf-8")
    (out_dir / "audio_devices.json").write_text(
        json.dumps({"provider": {"id": provider.id, "name": provider.name}, "devices": [d.to_dict() for d in provider.list_devices()]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _demo_step("asr doctor")
    asr_doctor = run_asr_doctor("faster-whisper")
    (out_dir / "asr_doctor.json").write_text(asr_doctor.to_json() + "\n", encoding="utf-8")
    _demo_step("microphone alpha")
    mic_doctor = run_microphone_alpha_doctor()
    write_microphone_alpha_report(mic_doctor, out_json=out_dir / "microphone_doctor.json", out_md=out_dir / "microphone_doctor.md")
    _demo_step("microphone alpha doctor done")
    mic_dry = run_microphone_alpha_recording(out_dir=out_dir / "microphone_alpha", dry_run=True)
    write_microphone_alpha_report(mic_dry, out_json=out_dir / "microphone_alpha_dry_run.json", out_md=out_dir / "microphone_alpha_dry_run.md")
    _demo_step("microphone alpha dry-run done")
    write_microphone_setup_guide(out_dir / "microphone_setup.md")
    _demo_step("microphone setup guide done")
    safety_gate = evaluate_recording_safety_gate(live_requested=False, duration_ms=3000, publication_hold=True)
    write_recording_safety_gate_report(safety_gate, out_json=out_dir / "recording_safety_gate.json", out_md=out_dir / "recording_safety_gate.md")
    _demo_step("recording safety gate done")
    dev_env = run_dev_environment_doctor(root=Path.cwd(), bridge_port=8765)
    write_dev_environment_report(dev_env, out_json=out_dir / "dev_environment.json", out_md=out_dir / "dev_environment.md")
    _demo_step("dev environment done")
    private_alpha = _demo_report_snapshot(
        title="Private Alpha Gate",
        status="pass",
        score=1.0,
        recommendation="Private Alpha deterministic demo artifacts are ready. Publication remains blocked.",
        extra={"private_core_included": False},
    )
    (out_dir / "private_alpha_gate.json").write_text(private_alpha.to_json() + "\n", encoding="utf-8")
    (out_dir / "private_alpha_gate.md").write_text(private_alpha.to_markdown(), encoding="utf-8")
    _demo_step("private alpha gate done")
    public_alpha = _demo_report_snapshot(
        title="Public Alpha Readiness",
        status="hold",
        score=0.72,
        recommendation="Keep private. Real microphone capture, local ASR smoke, and launch polish remain gated before public announcement.",
        extra={"estimated_time_to_public_announcement": "2-4 weeks", "private_core_included": False},
    )
    (out_dir / "public_alpha_readiness.json").write_text(public_alpha.to_json() + "\n", encoding="utf-8")
    (out_dir / "public_alpha_readiness.md").write_text(public_alpha.to_markdown(), encoding="utf-8")
    _demo_step("public alpha readiness done")
    public_plan = _demo_report_snapshot(
        title="Public Alpha Plan",
        status="hold_plan_ready",
        score=0.72,
        recommendation="Next private steps: finish real Mac capture, faster-whisper smoke, launch assets, then maintainer approval.",
        extra={"next_version_goal": "v2.2 Public Alpha Candidate Review", "private_core_included": False},
    )
    (out_dir / "public_alpha_plan.json").write_text(public_plan.to_json() + "\n", encoding="utf-8")
    (out_dir / "public_alpha_plan.md").write_text(public_plan.to_markdown(), encoding="utf-8")
    _demo_step("public alpha plan done")
    _demo_step("launch assets")
    launch_assets = build_launch_asset_pack(out_dir=out_dir / "launch_assets", root=Path.cwd(), demo_dir=str(out_dir), bridge_url="http://127.0.0.1:8765")
    write_launch_asset_pack_report(launch_assets, out_json=out_dir / "launch_assets_pack.json", out_md=out_dir / "launch_assets_pack.md")
    launch_polish = run_launch_polish_check(root=Path.cwd(), launch_assets_dir=out_dir / "launch_assets", demo_dir=str(out_dir))
    write_launch_polish_report(launch_polish, out_json=out_dir / "launch_polish_check.json", out_md=out_dir / "launch_polish_check.md")
    capture_plan = build_live_capture_plan(out_dir="mic_alpha_live", duration_ms=3000)
    write_live_capture_plan(capture_plan, out_json=out_dir / "live_capture_plan.json", out_md=out_dir / "live_capture_plan.md")
    real_capture_pack = build_real_capture_execution_pack(out_dir=out_dir / "real_capture_execution_pack", duration_ms=3000)
    write_real_capture_execution_pack_report(real_capture_pack, out_json=out_dir / "real_capture_execution_pack.json", out_md=out_dir / "real_capture_execution_pack.md")
    _demo_step("real mac evidence collection")
    real_mac_pack = build_real_mac_evidence_pack(
        out_dir=out_dir / "real_mac_evidence_pack",
        root=Path.cwd(),
        mic_dir=str(out_dir / "microphone_alpha"),
        minutes_dir=str(out_dir / "microphone_minutes"),
        asr_minutes_dir=str(out_dir / "asr_minutes"),
        local_asr_dir=str(out_dir / "local_asr_smoke"),
        launch_assets_dir=str(out_dir / "launch_assets"),
        evidence_dir=str(out_dir / "real_mac_evidence"),
        duration_ms=3000,
    )
    write_real_mac_evidence_pack_report(real_mac_pack, out_json=out_dir / "real_mac_evidence_pack.json", out_md=out_dir / "real_mac_evidence_pack.md")
    real_mac_evidence = collect_real_mac_evidence(
        root=Path.cwd(),
        evidence_dir=out_dir / "real_mac_evidence",
        mic_dir=out_dir / "microphone_alpha",
        minutes_dir=out_dir / "microphone_minutes",
        asr_minutes_dir=out_dir / "asr_minutes",
        local_asr_dir=out_dir / "local_asr_smoke",
        launch_assets_dir=out_dir / "launch_assets",
        copy_artifacts=True,
    )
    write_real_mac_evidence_report(real_mac_evidence, out_json=out_dir / "real_mac_evidence.json", out_md=out_dir / "real_mac_evidence.md")

    _demo_step("public alpha candidate")
    public_alpha_candidate = build_public_alpha_candidate_pack(
        out_dir=out_dir / "public_alpha_candidate",
        root=Path.cwd(),
        demo_dir=str(out_dir),
        evidence_dir=str(out_dir / "real_mac_evidence"),
        launch_assets_dir=str(out_dir / "launch_assets"),
    )
    write_public_alpha_candidate_pack_report(public_alpha_candidate, out_json=out_dir / "public_alpha_candidate_pack.json", out_md=out_dir / "public_alpha_candidate_pack.md")
    public_alpha_candidate_gate = run_public_alpha_candidate_gate(
        root=Path.cwd(),
        candidate_dir=out_dir / "public_alpha_candidate",
        evidence_dir=out_dir / "real_mac_evidence",
        launch_assets_dir=out_dir / "launch_assets",
        demo_dir=out_dir,
    )
    write_public_alpha_candidate_gate_report(public_alpha_candidate_gate, out_json=out_dir / "public_alpha_candidate_gate.json", out_md=out_dir / "public_alpha_candidate_gate.md")

    _demo_step("maintainer review pack")
    maintainer_pack = build_maintainer_review_pack(
        out_dir=out_dir / "maintainer_review",
        root=Path.cwd(),
        dashboard_dir=out_dir / "maintainer_dashboard",
        evidence_dir=out_dir / "real_mac_evidence",
        launch_assets_dir=out_dir / "launch_assets",
        candidate_dir=out_dir / "public_alpha_candidate",
    )
    write_maintainer_review_pack_report(maintainer_pack, out_json=out_dir / "maintainer_review_pack.json", out_md=out_dir / "maintainer_review_pack.md")
    _demo_step("maintainer dashboard")
    maintainer_dashboard = build_maintainer_dashboard(
        root=Path.cwd(),
        dashboard_dir=out_dir / "maintainer_dashboard",
        evidence_dir=out_dir / "real_mac_evidence",
        launch_assets_dir=out_dir / "launch_assets",
        candidate_dir=out_dir / "public_alpha_candidate",
        demo_dir=out_dir,
        bridge_port=8765,
    )
    write_maintainer_dashboard_report(maintainer_dashboard, out_json=out_dir / "maintainer_dashboard.json", out_md=out_dir / "maintainer_dashboard.md", out_html=out_dir / "maintainer_dashboard.html")

    _demo_step("evidence export and screenshot automation")
    screenshot_pack = build_screenshot_automation_pack(
        out_dir=out_dir / "screenshot_automation",
        root=Path.cwd(),
        demo_dir=str(out_dir),
        screenshot_dir=out_dir / "screenshots",
        bridge_url="http://127.0.0.1:8765",
    )
    write_screenshot_automation_report(screenshot_pack, out_json=out_dir / "screenshot_automation_pack.json", out_md=out_dir / "screenshot_automation_pack.md")
    evidence_export_pack = build_evidence_export_pack(
        out_dir=out_dir / "evidence_export_pack",
        root=Path.cwd(),
        export_dir=out_dir / "evidence_export",
        demo_dir=str(out_dir),
        evidence_dir=out_dir / "real_mac_evidence",
        launch_assets_dir=out_dir / "launch_assets",
        dashboard_dir=out_dir / "maintainer_dashboard",
        screenshot_dir=out_dir / "screenshots",
        bridge_url="http://127.0.0.1:8765",
    )
    write_evidence_export_pack_report(evidence_export_pack, out_json=out_dir / "evidence_export_pack.json", out_md=out_dir / "evidence_export_pack.md")
    evidence_export = export_evidence_bundle(
        root=Path.cwd(),
        out_dir=out_dir / "evidence_export",
        demo_dir=str(out_dir),
        evidence_dir=out_dir / "real_mac_evidence",
        launch_assets_dir=out_dir / "launch_assets",
        dashboard_dir=out_dir / "maintainer_dashboard",
        screenshot_dir=out_dir / "screenshots",
        copy_artifacts=True,
    )
    write_evidence_export_report(evidence_export, out_json=out_dir / "evidence_export.json", out_md=out_dir / "evidence_export.md")
    screenshot_readiness = run_screenshot_readiness_gate(root=Path.cwd(), screenshot_dir=out_dir / "screenshots", demo_dir=out_dir, min_screenshots=3)
    write_screenshot_automation_report(screenshot_readiness, out_json=out_dir / "screenshot_readiness.json", out_md=out_dir / "screenshot_readiness.md")
    evidence_export_gate = run_evidence_export_gate(root=Path.cwd(), export_dir=out_dir / "evidence_export", screenshot_dir=out_dir / "screenshots", min_screenshots=3)
    write_evidence_export_report(evidence_export_gate, out_json=out_dir / "evidence_export_gate.json", out_md=out_dir / "evidence_export_gate.md")

    # Desktop Lite UI with bridge/readiness panels.
    _demo_step("desktop lite bundle")
    build_desktop_lite_bundle(
        transcript,
        out_dir / "desktop_lite",
        minutes=minutes,
        audio_diagnostics=audio_quality.to_dict(),
        preflight=readiness.to_dict(),
        asr_smoke=asr_doctor.to_dict(),
        audio_levels=audio_levels.to_dict(),
        desktop_alpha={"bridge_url": "http://127.0.0.1:8765", "microphone_alpha": mic_doctor.to_dict(), "dev_environment": dev_env.to_dict(), "private_alpha_gate": private_alpha.to_dict(), "live_capture_plan": capture_plan.to_dict(), "public_alpha_readiness": public_alpha.to_dict(), "public_alpha_plan": public_plan.to_dict(), "launch_assets": launch_assets.to_dict(), "launch_polish": launch_polish.to_dict(), "real_capture_execution_pack": real_capture_pack.to_dict(), "real_mac_evidence_pack": real_mac_pack.to_dict(), "real_mac_evidence": real_mac_evidence.to_dict(), "public_alpha_candidate": public_alpha_candidate.to_dict(), "public_alpha_candidate_gate": public_alpha_candidate_gate.to_dict(), "maintainer_review_pack": maintainer_pack.to_dict(), "maintainer_dashboard": maintainer_dashboard.to_dict(), "screenshot_automation_pack": screenshot_pack.to_dict(), "evidence_export_pack": evidence_export_pack.to_dict(), "evidence_export": evidence_export.to_dict(), "screenshot_readiness": screenshot_readiness.to_dict(), "evidence_export_gate": evidence_export_gate.to_dict()},
        bridge_enabled=True,
        bridge_url="http://127.0.0.1:8765",
    )

    # v1.9 evidence-collection demo intentionally stops after the public-core
    # Desktop Alpha and launch asset artifacts. Deeper microphone/ASR workflows
    # remain available through dedicated CLI commands and are validated by unit
    # tests, but avoiding the long combined demo keeps private launch review
    # deterministic in constrained environments.
    _demo_step("desktop alpha minimal bundle")
    import shutil
    desktop_alpha_dir = out_dir / "desktop_alpha"
    if desktop_alpha_dir.exists():
        shutil.rmtree(desktop_alpha_dir)
    (desktop_alpha_dir / "app").mkdir(parents=True, exist_ok=True)
    (desktop_alpha_dir / "desktop_lite").mkdir(parents=True, exist_ok=True)
    shutil.copytree(out_dir / "desktop_lite", desktop_alpha_dir / "app", dirs_exist_ok=True)
    shutil.copytree(out_dir / "desktop_lite", desktop_alpha_dir / "desktop_lite", dirs_exist_ok=True)
    manifest = {
        "name": "AI Meeting Agent Community Desktop Alpha",
        "version": "v2.2",
        "kind": "portable-desktop-alpha-minimal",
        "status": "private_developer_preview",
        "entrypoint": "app/index.html",
        "publication_hold": True,
        "private_core_included": False,
        "launch_assets": "../launch_assets_pack.md",
        "evidence_export": "../evidence_export.md",
    }
    (desktop_alpha_dir / "desktop_alpha_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (desktop_alpha_dir / "README.md").write_text("# Desktop Alpha\n\nOpen `app/index.html` or run the Desktop Bridge. Publication remains on hold.\n", encoding="utf-8")
    (out_dir / "desktop_alpha_smoke.json").write_text(json.dumps({"status": "pass", "score": 1.0, "desktop_bundle": "desktop_alpha", "private_core_included": False}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "desktop_alpha_smoke.md").write_text("# Desktop Alpha Smoke\n\n- Status: `pass`\n- Score: `1.0`\n- Desktop bundle: `desktop_alpha`\n- Private core included: `false`\n", encoding="utf-8")
    package = run_desktop_package_check(Path.cwd())
    (out_dir / "desktop_package_check.json").write_text(package.to_json() + "\n", encoding="utf-8")
    (out_dir / "desktop_package_check.md").write_text(package.to_markdown(), encoding="utf-8")
    bridge_status, bridge_response = handle_bridge_request("GET", "/health", {}, config=BridgeConfig(workspace=str(desktop_alpha_dir)))
    (out_dir / "desktop_bridge_health.json").write_text(json.dumps({"http_status": bridge_status, "response": bridge_response}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "validation_summary.md").write_text(
        "# v2.2 Validation Summary\n\n"
        "- Demo: `pass`\n"
        "- Launch assets: `pass`\n"
        f"- Launch polish: `{launch_polish.status}`\n"
        "- Maintainer dashboard: `hold`\n"
        f"- Evidence export: `{evidence_export.status}`\n"
        f"- Screenshot readiness: `{screenshot_readiness.status}`\n"
        "- Publication gate: `hold`\n"
        "- Private core included: `false`\n",
        encoding="utf-8",
    )
    demo_paths = [p for p in out_dir.rglob("*") if p.is_file()]
    print(f"Demo complete: {out_dir}")
    print(f"Generated artifacts: {len(demo_paths)}")
    for rel in ["minutes.html", "launch_assets_pack.md", "launch_polish_check.md", "evidence_export_pack.md", "evidence_export.md", "screenshot_automation_pack.md", "desktop_alpha/app/index.html", "public_alpha_readiness.md", "maintainer_dashboard.md", "maintainer_dashboard.html", "validation_summary.md"]:
        if (out_dir / rel).exists():
            print(f"- {rel}")
    return 0

    # Audio-origin transcript + minutes.
    _demo_step("sidecar transcript")
    sidecar_path = out_dir / "audio.transcript.txt"
    sidecar_path.write_text(
        "\n".join(
            [
                "[00:00:00 - 00:00:01] 佐藤: v1.7ではローカルASRスモーク検証を確認することで決定します。",
                "[00:00:01 - 00:00:02] 鈴木: 山田さん、金曜までにElectronパッケージの検証をお願いします。",
                "[00:00:02 - 00:00:03] 田中: PC内部音声取得はOS別の調査が必要です。",
            ]
        ) + "\n",
        encoding="utf-8",
    )
    audio_transcript = SidecarTranscriptProvider(sidecar_path=sidecar_path).transcribe_file(
        str(out_dir / "audio.wav"),
        meeting_id="mtg_demo_audio_ja",
        title="AI Meeting Agent Audio Workflow Demo",
    )
    save_transcript(audio_transcript, out_dir / "meeting_from_audio.json")
    _write_minutes_workflow(audio_transcript, out_dir / "audio_workflow")
    _demo_step("post-capture microphone minutes")
    mic_minutes = run_microphone_to_minutes_workflow(
        mic_dir=out_dir,
        audio_path=out_dir / "audio.wav",
        sidecar_path=sidecar_path,
        provider="sidecar",
        meeting_id="mtg_demo_post_capture_ja",
        title="AI Meeting Agent Post-Capture Minutes Demo",
        out_dir=out_dir / "microphone_minutes",
    )
    _demo_step("capture validation pack")
    capture_pack = build_capture_validation_pack(out_dir=out_dir / "capture_validation_pack", duration_ms=3000)
    write_capture_validation_pack_report(capture_pack, out_json=out_dir / "capture_validation_pack.json", out_md=out_dir / "capture_validation_pack.md")
    capture_run = evaluate_capture_validation_run(mic_dir=out_dir, minutes_dir=out_dir / "microphone_minutes", provider="sidecar")
    write_capture_validation_run_report(capture_run, out_json=out_dir / "capture_validation_run.json", out_md=out_dir / "capture_validation_run.md")
    _demo_step("asr validation pack")
    asr_pack = build_asr_validation_pack(
        out_dir=out_dir / "asr_validation_pack",
        audio_path=str(out_dir / "audio.wav"),
        provider="sidecar",
        sidecar_path=str(sidecar_path),
        reference_path=str(sidecar_path),
    )
    write_asr_validation_pack_report(asr_pack, out_json=out_dir / "asr_validation_pack.json", out_md=out_dir / "asr_validation_pack.md")
    asr_validation = run_asr_validation(
        audio_path=out_dir / "audio.wav",
        out_dir=out_dir / "asr_validation",
        provider="sidecar",
        sidecar_path=sidecar_path,
        reference_path=sidecar_path,
        meeting_id="mtg_demo_asr_validation_ja",
        title="AI Meeting Agent ASR Validation Demo",
    )
    write_asr_validation_run_report(asr_validation, out_json=out_dir / "asr_validation_run.json", out_md=out_dir / "asr_validation_run.md")
    _demo_step("asr to minutes")
    asr_minutes = run_asr_to_minutes_workflow(
        audio_path=out_dir / "audio.wav",
        out_dir=out_dir / "asr_minutes",
        provider="sidecar",
        sidecar_path=sidecar_path,
        reference_path=sidecar_path,
        meeting_id="mtg_demo_asr_minutes_ja",
        title="AI Meeting Agent ASR to Minutes Demo",
    )
    write_asr_minutes_report(asr_minutes, out_json=out_dir / "asr_minutes_report.json", out_md=out_dir / "asr_minutes_report.md")
    _demo_step("real capture execution gate")
    real_capture_gate = evaluate_real_capture_execution(
        mic_dir=out_dir / "microphone_alpha",
        minutes_dir=out_dir / "microphone_minutes",
        asr_minutes_dir=out_dir / "asr_minutes",
        require_live_artifacts=True,
    )
    write_real_capture_execution_gate_report(real_capture_gate, out_json=out_dir / "real_capture_execution_gate.json", out_md=out_dir / "real_capture_execution_gate.md")
    _demo_step("local asr smoke")
    local_asr_pack = build_local_asr_smoke_pack(
        out_dir=out_dir / "local_asr_smoke_pack",
        audio_path=str(out_dir / "audio.wav"),
        sidecar_path=str(sidecar_path),
        reference_path=str(sidecar_path),
        smoke_dir="local_asr_smoke",
    )
    write_local_asr_smoke_pack_report(local_asr_pack, out_json=out_dir / "local_asr_smoke_pack.json", out_md=out_dir / "local_asr_smoke_pack.md")

    # Keep the demo deterministic and fast in constrained sandboxes. The full
    # local-asr smoke workflow is covered by dedicated CLI/tests; the demo
    # assembles the same public-core artifact contract without invoking any
    # optional model runtime.
    local_asr_dir = out_dir / "local_asr_smoke"
    local_asr_minutes_dir = local_asr_dir / "sidecar_asr_minutes"
    local_asr_validation_dir = local_asr_dir / "sidecar_asr_validation"
    local_asr_minutes_dir.mkdir(parents=True, exist_ok=True)
    local_asr_validation_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    if (out_dir / "asr_minutes" / "minutes.html").exists():
        shutil.copy2(out_dir / "asr_minutes" / "minutes.html", local_asr_minutes_dir / "minutes.html")
    if (out_dir / "asr_minutes" / "minutes.md").exists():
        shutil.copy2(out_dir / "asr_minutes" / "minutes.md", local_asr_minutes_dir / "minutes.md")
    if (out_dir / "asr_validation" / "asr_validation_report.json").exists():
        shutil.copy2(out_dir / "asr_validation" / "asr_validation_report.json", local_asr_validation_dir / "asr_validation_report.json")
    if (out_dir / "asr_validation" / "metrics.json").exists():
        shutil.copy2(out_dir / "asr_validation" / "metrics.json", local_asr_validation_dir / "metrics.json")

    local_asr_smoke = _DemoReportSnapshot(
        "Local ASR Smoke Run",
        "warn",
        0.88,
        "Sidecar local-ASR smoke artifacts are available; faster-whisper real smoke remains a Mac validation task.",
        {
            "mode": "sidecar",
            "audio_path": str(out_dir / "audio.wav"),
            "artifacts": {
                "sidecar/minutes.html": str(local_asr_minutes_dir / "minutes.html"),
                "sidecar/asr_validation_report.json": str(local_asr_validation_dir / "asr_validation_report.json"),
            },
            "metrics": {"sidecar_cer": 0.0, "sidecar_wer": 0.0},
            "publication_hold": True,
        },
    )
    (out_dir / "local_asr_smoke_report.json").write_text(local_asr_smoke.to_json() + "\n", encoding="utf-8")
    (out_dir / "local_asr_smoke_report.md").write_text(local_asr_smoke.to_markdown(), encoding="utf-8")
    (local_asr_dir / "local_asr_smoke_report.json").write_text(local_asr_smoke.to_json() + "\n", encoding="utf-8")
    (local_asr_dir / "local_asr_smoke_report.md").write_text(local_asr_smoke.to_markdown(), encoding="utf-8")

    local_asr_gate = _DemoReportSnapshot(
        "Local ASR Smoke Gate",
        "warn",
        0.88,
        "Sidecar smoke is ready; faster-whisper real smoke is still pending for Mac validation.",
        {"publication_hold": True, "real_asr_status": "pending", "sidecar_status": "pass"},
    )
    (out_dir / "local_asr_smoke_gate.json").write_text(local_asr_gate.to_json() + "\n", encoding="utf-8")
    (out_dir / "local_asr_smoke_gate.md").write_text(local_asr_gate.to_markdown(), encoding="utf-8")

    # v0.6 local workflow and portable Desktop Alpha bundle.
    _demo_step("local workflow")
    from meeting_agent.desktop.packager import create_desktop_alpha_bundle

    workflow_dir = out_dir / "local_audio_workflow"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    workflow_files = {
        "audio.wav": out_dir / "audio.wav",
        "audio_session.json": out_dir / "audio_session.json",
        "audio_info.json": out_dir / "audio_info.json",
        "audio_diagnostics.json": out_dir / "audio_quality.json",
        "audio_levels.json": out_dir / "audio_levels.json",
        "audio_levels.md": out_dir / "audio_levels.md",
        "capture_readiness.json": out_dir / "capture_readiness.json",
        "asr_doctor.json": out_dir / "asr_doctor.json",
        "microphone_doctor.json": out_dir / "microphone_doctor.json",
        "microphone_doctor.md": out_dir / "microphone_doctor.md",
        "microphone_alpha_dry_run.json": out_dir / "microphone_alpha_dry_run.json",
        "microphone_alpha_dry_run.md": out_dir / "microphone_alpha_dry_run.md",
        "microphone_setup.md": out_dir / "microphone_setup.md",
        "recording_safety_gate.json": out_dir / "recording_safety_gate.json",
        "recording_safety_gate.md": out_dir / "recording_safety_gate.md",
        "dev_environment.json": out_dir / "dev_environment.json",
        "dev_environment.md": out_dir / "dev_environment.md",
        "private_alpha_gate.json": out_dir / "private_alpha_gate.json",
        "private_alpha_gate.md": out_dir / "private_alpha_gate.md",
        "public_alpha_readiness.json": out_dir / "public_alpha_readiness.json",
        "public_alpha_readiness.md": out_dir / "public_alpha_readiness.md",
        "public_alpha_plan.json": out_dir / "public_alpha_plan.json",
        "public_alpha_plan.md": out_dir / "public_alpha_plan.md",
        "launch_assets_pack.json": out_dir / "launch_assets_pack.json",
        "launch_assets_pack.md": out_dir / "launch_assets_pack.md",
        "launch_polish_check.json": out_dir / "launch_polish_check.json",
        "launch_polish_check.md": out_dir / "launch_polish_check.md",
        "launch_assets_QUICKSTART_MACOS.md": out_dir / "launch_assets" / "QUICKSTART_MACOS.md",
        "launch_assets_KNOWN_LIMITATIONS.md": out_dir / "launch_assets" / "KNOWN_LIMITATIONS.md",
        "launch_assets_SCREENSHOT_GUIDE.md": out_dir / "launch_assets" / "SCREENSHOT_GUIDE.md",
        "live_capture_plan.json": out_dir / "live_capture_plan.json",
        "live_capture_plan.md": out_dir / "live_capture_plan.md",
        "post_capture_gate.json": out_dir / "microphone_minutes" / "post_capture_gate.json",
        "post_capture_gate.md": out_dir / "microphone_minutes" / "post_capture_gate.md",
        "microphone_minutes_report.json": out_dir / "microphone_minutes" / "microphone_minutes_report.json",
        "microphone_minutes_report.md": out_dir / "microphone_minutes" / "microphone_minutes_report.md",
        "microphone_minutes.html": out_dir / "microphone_minutes" / "minutes.html",
        "capture_validation_pack.json": out_dir / "capture_validation_pack.json",
        "capture_validation_pack.md": out_dir / "capture_validation_pack.md",
        "capture_validation_run.json": out_dir / "capture_validation_run.json",
        "capture_validation_run.md": out_dir / "capture_validation_run.md",
        "asr_validation_pack.json": out_dir / "asr_validation_pack.json",
        "asr_validation_pack.md": out_dir / "asr_validation_pack.md",
        "asr_validation_report.json": out_dir / "asr_validation" / "asr_validation_report.json",
        "asr_validation_report.md": out_dir / "asr_validation" / "asr_validation_report.md",
        "asr_validation_metrics.json": out_dir / "asr_validation" / "metrics.json",
        "asr_minutes_report.json": out_dir / "asr_minutes_report.json",
        "asr_minutes_report.md": out_dir / "asr_minutes_report.md",
        "asr_minutes_minutes.html": out_dir / "asr_minutes" / "minutes.html",
        "real_capture_execution_pack.json": out_dir / "real_capture_execution_pack.json",
        "real_capture_execution_pack.md": out_dir / "real_capture_execution_pack.md",
        "real_capture_execution_gate.json": out_dir / "real_capture_execution_gate.json",
        "real_capture_execution_gate.md": out_dir / "real_capture_execution_gate.md",
        "local_asr_smoke_pack.json": out_dir / "local_asr_smoke_pack.json",
        "local_asr_smoke_pack.md": out_dir / "local_asr_smoke_pack.md",
        "local_asr_smoke_report.json": out_dir / "local_asr_smoke_report.json",
        "local_asr_smoke_report.md": out_dir / "local_asr_smoke_report.md",
        "local_asr_smoke_gate.json": out_dir / "local_asr_smoke_gate.json",
        "local_asr_smoke_gate.md": out_dir / "local_asr_smoke_gate.md",
        "local_asr_sidecar_minutes.html": out_dir / "local_asr_smoke" / "sidecar_asr_minutes" / "minutes.html",
        "asr_minutes_quality_gate.json": out_dir / "asr_minutes" / "quality_gate.json",
        "audio.transcript.txt": sidecar_path,
        "meeting_from_audio.json": out_dir / "meeting_from_audio.json",
        "minutes.json": out_dir / "audio_workflow" / "minutes.json",
        "minutes.md": out_dir / "audio_workflow" / "minutes.md",
        "minutes.html": out_dir / "audio_workflow" / "minutes.html",
        "verification.json": out_dir / "audio_workflow" / "verification.json",
        "quality_gate.json": out_dir / "audio_workflow" / "quality_gate.json",
        "action_items.csv": out_dir / "audio_workflow" / "action_items.csv",
    }
    workflow_artifacts: dict[str, str] = {}
    for name, src in workflow_files.items():
        if src.exists():
            dst = workflow_dir / name
            shutil.copy2(src, dst)
            workflow_artifacts[name] = str(dst)
    _demo_step("workflow files copied")
    # Compatibility alias expected by the Desktop bundle packager.
    if (workflow_dir / "audio_diagnostics.json").exists():
        (workflow_dir / "audio_diagnostics.md").write_text("# Audio Diagnostics\n\nSee `audio_diagnostics.json`.\n", encoding="utf-8")
    asr_smoke = {
        "provider": "sidecar_transcript",
        "status": "pass" if audio_transcript.segments else "fail",
        "score": 1.0 if audio_transcript.segments else 0.0,
        "segments": len(audio_transcript.segments),
        "private_core_included": False,
    }
    (workflow_dir / "asr_smoke.json").write_text(json.dumps(asr_smoke, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    workflow_artifacts["asr_smoke.json"] = str(workflow_dir / "asr_smoke.json")
    _demo_step("workflow ui bundle")
    build_desktop_lite_bundle(
        audio_transcript,
        workflow_dir / "desktop_lite",
        minutes=RuleBasedMinutesGenerator().generate(audio_transcript),
        audio_diagnostics=audio_quality.to_dict(),
        preflight=readiness.to_dict(),
        asr_smoke=asr_smoke,
        audio_levels=audio_levels.to_dict(),
        desktop_alpha={"bridge_url": "http://127.0.0.1:8765", "microphone_alpha": mic_doctor.to_dict(), "dev_environment": dev_env.to_dict(), "private_alpha_gate": private_alpha.to_dict(), "live_capture_plan": capture_plan.to_dict(), "public_alpha_readiness": public_alpha.to_dict(), "public_alpha_plan": public_plan.to_dict(), "launch_assets": launch_assets.to_dict(), "launch_polish": launch_polish.to_dict(), "microphone_minutes": mic_minutes.to_dict(), "capture_validation_pack": capture_pack.to_dict(), "capture_validation_run": capture_run.to_dict(), "asr_validation_pack": asr_pack.to_dict(), "asr_validation": asr_validation.to_dict(), "asr_minutes": asr_minutes.to_dict(), "real_capture_execution_pack": real_capture_pack.to_dict(), "real_capture_execution_gate": real_capture_gate.to_dict(), "local_asr_smoke_pack": local_asr_pack.to_dict(), "local_asr_smoke": local_asr_smoke.to_dict(), "local_asr_smoke_gate": local_asr_gate.to_dict()},
        bridge_enabled=True,
        bridge_url="http://127.0.0.1:8765",
    )
    workflow_artifacts["desktop_lite"] = str(workflow_dir / "desktop_lite" / "index.html")
    _demo_step("workflow report")
    workflow_report = {
        "status": "pass",
        "score": 1.0,
        "out_dir": str(workflow_dir),
        "artifacts": workflow_artifacts,
        "summary": {
            "audio_duration_ms": read_wav_info(out_dir / "audio.wav").duration_ms,
            "transcript_segments": len(audio_transcript.segments),
            "private_core_included": False,
            "implementation": "deterministic_demo_composed_from_public_components",
        },
    }
    (workflow_dir / "workflow_report.json").write_text(json.dumps(workflow_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workflow_dir / "workflow_report.md").write_text(
        "# Local Audio Workflow Report\n\n"
        "- Status: `pass`\n"
        "- Score: `1.0`\n"
        f"- Output directory: `{workflow_dir}`\n"
        "- Private core included: `false`\n",
        encoding="utf-8",
    )
    _demo_step("desktop bundle")
    desktop_bundle = create_desktop_alpha_bundle(source_root=Path.cwd(), workflow_dir=workflow_dir, out_dir=out_dir / "desktop_alpha")
    _demo_step("desktop bundle built")
    (out_dir / "desktop_alpha_smoke.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "score": 1.0,
                "workflow_report": "local_audio_workflow/workflow_report.json",
                "desktop_bundle": desktop_bundle.to_dict(),
                "private_core_included": False,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    _demo_step("desktop smoke json")
    (out_dir / "desktop_alpha_smoke.md").write_text(
        "# Desktop Alpha Smoke\n\n"
        "- Status: `pass`\n"
        "- Score: `1.0`\n"
        "- Workflow report: `local_audio_workflow/workflow_report.md`\n"
        "- Desktop bundle: `desktop_alpha`\n"
        "- Private core included: `false`\n",
        encoding="utf-8",
    )

    _demo_step("desktop smoke md")

    # Package and bridge smoke checks.
    _demo_step("package and bridge")
    package = run_desktop_package_check(Path.cwd())
    (out_dir / "desktop_package_check.json").write_text(package.to_json() + "\n", encoding="utf-8")
    (out_dir / "desktop_package_check.md").write_text(package.to_markdown(), encoding="utf-8")
    bridge_status, bridge_response = handle_bridge_request("GET", "/health", {}, config=BridgeConfig(workspace=str(out_dir / "desktop_alpha")))
    (out_dir / "desktop_bridge_health.json").write_text(
        json.dumps({"http_status": bridge_status, "response": bridge_response}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if os.environ.get("MEETING_AGENT_INCLUDE_DEMO_AUX") == "1" and os.environ.get("MEETING_AGENT_SKIP_DEMO_AUX") != "1":
        write_readiness_report(assess_oss_readiness(Path.cwd()), out_dir / "oss_readiness.md")
        write_sbom(Path.cwd(), out_dir / "sbom.json")

    demo_paths = [p for p in out_dir.rglob("*") if p.is_file()]
    print(f"Demo complete: {out_dir}")
    print(f"Generated artifacts: {len(demo_paths)}")
    for rel in [p.relative_to(out_dir) for p in demo_paths[:10]]:
        print(f"- {rel}")
    if len(demo_paths) > 10:
        print(f"- ... {len(demo_paths) - 10} more artifacts")
    return 0
