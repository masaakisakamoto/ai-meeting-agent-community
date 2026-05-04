from __future__ import annotations

import json
import mimetypes
import re
import webbrowser
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlparse

from meeting_agent import __version__
from meeting_agent.audio.live_guard import LIVE_CONFIRMATION_PHRASE, evaluate_recording_safety_gate
from meeting_agent.audio.capture_plan import build_live_capture_plan
from meeting_agent.audio.validation_pack import build_capture_validation_pack, evaluate_capture_validation_run
from meeting_agent.env.dev_environment import run_dev_environment_doctor
from meeting_agent.release.private_alpha import run_private_alpha_gate
from meeting_agent.release.public_alpha import build_public_alpha_plan, run_public_alpha_readiness
from meeting_agent.release.public_alpha_candidate import build_public_alpha_candidate_pack, run_public_alpha_candidate_gate
from meeting_agent.release.maintainer_dashboard import build_maintainer_review_pack, build_maintainer_dashboard
from meeting_agent.audio.microphone_alpha import run_microphone_alpha_doctor, run_microphone_alpha_recording
from meeting_agent.desktop.workspace import DesktopAlphaManager
from meeting_agent.providers.audio import SimulatedAudioCaptureProvider, SoundDeviceMicrophoneProvider
from meeting_agent.workflows.local_audio import default_sidecar_text, run_local_audio_workflow
from meeting_agent.workflows.microphone_minutes import evaluate_post_capture_gate, run_microphone_to_minutes_workflow
from meeting_agent.workflows.asr_minutes import run_asr_to_minutes_workflow
from meeting_agent.workflows.asr_validation import build_asr_validation_pack, run_asr_validation
from meeting_agent.workflows.real_capture_execution import build_real_capture_execution_pack, evaluate_real_capture_execution
from meeting_agent.workflows.local_asr_smoke import (
    build_local_asr_smoke_pack,
    evaluate_local_asr_smoke_gate,
    run_local_asr_smoke,
)
from meeting_agent.release.launch_assets import build_launch_asset_pack, run_launch_polish_check
from meeting_agent.release.evidence_collection import build_real_mac_evidence_pack, collect_real_mac_evidence
from meeting_agent.release.evidence_export import (
    build_evidence_export_pack,
    build_screenshot_automation_pack,
    export_evidence_bundle,
    run_evidence_export_gate,
    run_screenshot_readiness_gate,
)


@dataclass
class DesktopBridgeConfig:
    workspace: Path | str
    static_dir: Path | str | None = None
    host: str = "127.0.0.1"
    port: int = 8765

    def __post_init__(self) -> None:
        self.workspace = Path(self.workspace)
        self.static_dir = Path(self.static_dir) if self.static_dir else None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["workspace"] = str(self.workspace)
        payload["static_dir"] = str(_resolve_static_dir(self))
        return payload


BridgeConfig = DesktopBridgeConfig


def _candidate_static_dirs(config: DesktopBridgeConfig) -> list[Path]:
    candidates: list[Path] = []
    if config.static_dir:
        candidates.append(Path(config.static_dir))
    candidates.extend([Path(config.workspace) / "app", Path(config.workspace) / "desktop_lite"])
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def _resolve_static_dir(config: DesktopBridgeConfig) -> Path:
    for candidate in _candidate_static_dirs(config):
        if (candidate / "index.html").exists():
            return candidate
    return _candidate_static_dirs(config)[0]


def _ensure_workspace(config: DesktopBridgeConfig) -> None:
    config.workspace.mkdir(parents=True, exist_ok=True)
    if not any((candidate / "index.html").exists() for candidate in _candidate_static_dirs(config)):
        DesktopAlphaManager(config.workspace).initialize(bridge_host=config.host, bridge_port=config.port)


def _health_payload(config: DesktopBridgeConfig) -> dict[str, Any]:
    static_dir = _resolve_static_dir(config)
    return {
        "status": "ok",
        "project": "ai-meeting-agent-community",
        "bridge": "desktop-alpha",
        "version": __version__,
        "workspace": str(config.workspace),
        "static_dir": str(static_dir),
        "private_core_included": False,
        "ui": {"root": "/", "app": "/app", "index": "/index.html", "served_from": str(static_dir), "served_by_bridge": True},
        "routes": [
            "/",
            "/app",
            "/index.html",
            "/workspace/<path>",
            "/health",
            "/api/health",
            "/api/workspace",
            "/api/audio/devices",
            "/api/devices",
            "/api/manifest",
            "/api/workflows/last",
            "/api/workflows/latest",
            "/api/recording/safety-gate",
            "/api/dev/environment",
            "/api/private-alpha/gate",
            "/api/public-alpha/readiness",
            "/api/public-alpha/plan",
            "/api/public-alpha/candidate-pack",
            "/api/public-alpha/candidate-gate",
            "/api/maintainer/review-pack",
            "/api/maintainer/dashboard",
            "/api/real-capture/execution-pack",
            "/api/real-capture/execution-gate",
            "/api/local-asr/smoke-pack",
            "/api/local-asr/smoke-run",
            "/api/local-asr/smoke-gate",
            "/api/launch/assets-pack",
            "/api/launch/assets-gate",
            "/api/launch/polish-check",
            "/api/evidence/real-mac-pack",
            "/api/evidence/real-mac-collect",
            "/api/evidence/export-pack",
            "/api/evidence/export-run",
            "/api/evidence/export-gate",
            "/api/screenshots/automation-pack",
            "/api/screenshots/readiness-gate",
            "/api/capture/plan",
            "/api/capture/validation-pack",
            "/api/capture/validation-run",
            "/api/asr/validation-pack",
            "/api/asr/validation-run",
            "/api/workflows/asr-to-minutes",
            "/api/post-capture/gate",
            "/api/workflows/microphone-to-minutes",
            "/api/microphone/doctor",
            "/api/microphone/preflight",
            "/api/workflows/microphone-alpha",
            "/api/workflows/simulated-record",
            "/api/workflows/simulated-recording",
        ],
    }


def _workspace_payload(config: DesktopBridgeConfig) -> dict[str, Any]:
    workspace = Path(config.workspace)
    files: list[dict[str, Any]] = []
    if workspace.exists():
        for path in sorted(workspace.rglob("*")):
            if path.is_file() and len(files) < 300:
                files.append({"path": str(path.relative_to(workspace)), "bytes": path.stat().st_size})
    return {"status": "ok", "workspace": str(workspace), "files": files, "last_workflow": _read_last_workflow(config), "private_core_included": False}


def _devices_payload(provider_id: str = "simulated") -> dict[str, Any]:
    try:
        provider = SoundDeviceMicrophoneProvider() if provider_id == "microphone" else SimulatedAudioCaptureProvider()
        devices = [device.to_dict() for device in provider.list_devices()]
        return {"status": "ok", "provider": {"id": provider.id, "name": provider.name}, "devices": devices, "device_count": len(devices), "private_core_included": False}
    except Exception as exc:
        return {"status": "warn", "provider": provider_id, "devices": [], "device_count": 0, "error": str(exc), "private_core_included": False}


def _workflow_manifest_path(config: DesktopBridgeConfig) -> Path:
    return Path(config.workspace) / "last_bridge_workflow.json"


def _read_last_workflow(config: DesktopBridgeConfig) -> dict[str, Any] | None:
    path = _workflow_manifest_path(config)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "warn", "error": "last workflow manifest is not valid JSON", "private_core_included": False}


def _safe_run_id(value: str | None) -> str:
    raw = (value or "ui_sim").strip() or "ui_sim"
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", raw)[:80]


def _relative_artifacts(workspace: Path, artifacts: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in artifacts.items():
        path = Path(value)
        try:
            result[key] = str(path.relative_to(workspace))
        except ValueError:
            result[key] = str(path)
    return result


def _bridge_workflow_steps(summary: dict[str, Any], status: str) -> list[dict[str, str]]:
    step_status = "pass" if status in {"pass", "ok"} else status
    return [
        {"name": "capture preflight", "status": step_status, "detail": str(summary.get("capture_readiness_status", "simulated"))},
        {"name": "WAV recording", "status": step_status, "detail": f"{summary.get('audio_duration_ms', '-')} ms"},
        {"name": "audio diagnostics", "status": step_status, "detail": str(summary.get("audio_quality_status", "-"))},
        {"name": "ASR smoke", "status": step_status, "detail": f"segments {summary.get('transcript_segments', '-')}"},
        {"name": "transcript", "status": step_status, "detail": f"segments {summary.get('transcript_segments', '-')}"},
        {"name": "minutes", "status": step_status, "detail": f"decisions {summary.get('decisions', '-')} / actions {summary.get('action_items', '-')}"},
        {"name": "desktop bundle", "status": step_status, "detail": "public Community UI refreshed"},
    ]


def _run_simulated_recording_workflow(config: DesktopBridgeConfig, payload: dict[str, Any]) -> dict[str, Any]:
    workspace = Path(config.workspace)
    session_id = _safe_run_id(str(payload.get("session_id") or payload.get("run_id") or "ui_sim"))
    total_ms = max(500, min(int(payload.get("total_ms") or 3000), 60_000))
    chunk_ms = max(50, min(int(payload.get("chunk_ms") or 250), 5000))
    run_dir = workspace / "bridge_runs" / session_id
    result = run_local_audio_workflow(
        run_dir,
        session_id=session_id,
        total_ms=total_ms,
        chunk_ms=chunk_ms,
        meeting_id=f"mtg_bridge_{session_id}",
        title="AI Meeting Agent Bridge Simulated Recording",
        sidecar_text=default_sidecar_text("v0.9"),
    )
    manager = DesktopAlphaManager(config.workspace)
    desktop_paths = manager.initialize(bridge_host=config.host, bridge_port=config.port)
    artifacts = _relative_artifacts(workspace, result.artifacts)
    artifacts.update({f"desktop_{name}": str(Path(path).relative_to(workspace)) if Path(path).is_relative_to(workspace) else str(path) for name, path in desktop_paths.items()})
    workflow_payload: dict[str, Any] = {
        "id": "simulated-recording-local-audio-workflow",
        "status": result.status,
        "score": result.score,
        "run_id": session_id,
        "run_dir": str(run_dir.relative_to(workspace)),
        "summary": result.summary,
        "artifacts": artifacts,
        "steps": _bridge_workflow_steps(result.summary, result.status),
        "private_core_included": False,
        "public_core_only": True,
    }
    _workflow_manifest_path(config).write_text(json.dumps({"status": "ok", "workflow": workflow_payload}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return workflow_payload




def _default_post_capture_audio(config: DesktopBridgeConfig) -> Path:
    workspace = Path(config.workspace)
    candidates = [
        workspace / "audio.wav",
        workspace / "artifacts" / "audio.wav",
        workspace / "local_audio_workflow" / "audio.wav",
        workspace / "microphone_alpha" / "audio.wav",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _default_post_capture_sidecar(config: DesktopBridgeConfig) -> Path | None:
    workspace = Path(config.workspace)
    candidates = [
        workspace / "audio.transcript.txt",
        workspace / "artifacts" / "audio.transcript.txt",
        workspace / "artifacts" / "meeting_from_audio.json",
        workspace / "app" / "transcript.json",
        workspace / "desktop_lite" / "transcript.json",
        workspace / "local_audio_workflow" / "audio.transcript.txt",
        workspace / "local_audio_workflow" / "meeting_from_audio.json",
        workspace / "microphone_alpha" / "audio.transcript.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _run_microphone_to_minutes_bridge_workflow(config: DesktopBridgeConfig, payload: dict[str, Any]) -> dict[str, Any]:
    workspace = Path(config.workspace)
    run_id = _safe_run_id(str(payload.get("run_id") or payload.get("session_id") or "ui_mic_minutes"))
    out_dir = workspace / "bridge_runs" / run_id / "microphone_minutes"
    audio_path = Path(payload["audio_path"]) if payload.get("audio_path") else _default_post_capture_audio(config)
    sidecar = Path(payload["sidecar"]) if payload.get("sidecar") else _default_post_capture_sidecar(config)
    report = run_microphone_to_minutes_workflow(
        mic_dir=workspace,
        out_dir=out_dir,
        audio_path=audio_path,
        provider=str(payload.get("provider", "sidecar")),
        sidecar_path=sidecar,
        meeting_id=str(payload.get("meeting_id", f"mtg_bridge_mic_minutes_{run_id}")),
        title=str(payload.get("title", "AI Meeting Agent Microphone to Minutes")),
        model_size=str(payload.get("model_size", "small")),
        device=str(payload.get("device", "cpu")),
        compute_type=str(payload.get("compute_type", "int8")),
    )
    workflow = {
        "id": "microphone-to-minutes-post-capture",
        "status": "pass" if report.status in {"pass", "warn"} else "fail",
        "score": report.score,
        "run_id": run_id,
        "run_dir": str(out_dir.relative_to(workspace)) if out_dir.is_relative_to(workspace) else str(out_dir),
        "mode": report.mode,
        "summary": report.summary,
        "steps": [check.to_dict() for check in report.checks],
        "artifacts": _relative_artifacts(workspace, report.artifacts),
        "next_actions": [report.recommendation],
        "microphone_minutes": report.to_dict(),
        "private_core_included": False,
        "public_core_only": True,
    }
    _workflow_manifest_path(config).write_text(json.dumps({"status": "ok", "workflow": workflow}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return workflow

def handle_bridge_request(method: str, path: str, payload: dict[str, Any] | None = None, *, config: DesktopBridgeConfig | None = None) -> tuple[int, dict[str, Any]]:
    config = config or DesktopBridgeConfig(workspace=Path(".meeting-agent-desktop-alpha"))
    _ensure_workspace(config)
    payload = payload or {}
    parsed = urlparse(path)
    route = parsed.path or "/"
    method = method.upper()
    if method == "GET" and route in {"/health", "/api/health"}:
        return 200, _health_payload(config)
    if method == "GET" and route == "/api/workspace":
        return 200, _workspace_payload(config)
    if method == "GET" and route in {"/api/audio/devices", "/api/devices"}:
        params = parse_qs(parsed.query)
        provider_id = (params.get("provider") or [payload.get("provider", "simulated")])[0]
        return 200, _devices_payload(provider_id)
    if method == "GET" and route == "/api/dev/environment":
        report = run_dev_environment_doctor(root=Path.cwd(), bridge_port=config.port)
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "environment": report.to_dict(), "private_core_included": False}
    if method == "GET" and route == "/api/private-alpha/gate":
        report = run_private_alpha_gate(root=Path.cwd(), run_tests=False, bridge_port=config.port)
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "private_alpha_gate": report.to_dict(), "private_core_included": False}
    if method == "GET" and route == "/api/public-alpha/readiness":
        report = run_public_alpha_readiness(root=Path.cwd(), bridge_port=config.port)
        return 200, {"status": "ok" if report.status in {"hold", "ready_with_warnings_but_publication_hold", "candidate_but_publication_hold"} else "fail", "public_alpha_readiness": report.to_dict(), "private_core_included": False}
    if method == "GET" and route == "/api/public-alpha/plan":
        report = build_public_alpha_plan(root=Path.cwd(), bridge_port=config.port)
        return 200, {"status": "ok" if report.status in {"hold_plan_ready", "ready"} else "fail", "public_alpha_plan": report.to_dict(), "private_core_included": False}
    if method == "GET" and route == "/api/public-alpha/candidate-pack":
        params = parse_qs(parsed.query)
        out_dir = Path(config.workspace) / ((params.get("out_dir") or ["public_alpha_candidate"])[0])
        report = build_public_alpha_candidate_pack(
            out_dir=out_dir,
            root=Path.cwd(),
            demo_dir=(params.get("demo_dir") or ["demo_out"])[0],
            evidence_dir=(params.get("evidence_dir") or ["real_mac_evidence"])[0],
            launch_assets_dir=(params.get("launch_assets_dir") or ["launch_assets"])[0],
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "public_alpha_candidate_pack": report.to_dict(), "private_core_included": False}
    if method == "GET" and route == "/api/public-alpha/candidate-gate":
        params = parse_qs(parsed.query)
        report = run_public_alpha_candidate_gate(
            root=Path.cwd(),
            candidate_dir=Path(config.workspace) / ((params.get("candidate_dir") or ["public_alpha_candidate"])[0]),
            evidence_dir=(params.get("evidence_dir") or ["real_mac_evidence"])[0],
            launch_assets_dir=(params.get("launch_assets_dir") or ["launch_assets"])[0],
            demo_dir=(params.get("demo_dir") or ["demo_out"])[0],
            bridge_port=config.port,
        )
        return 200, {"status": "ok" if report.status in {"hold_missing_candidate_evidence", "candidate_ready_but_publication_hold", "candidate_policy_unlocked_review_required"} else "fail", "public_alpha_candidate_gate": report.to_dict(), "private_core_included": False}
    if method == "GET" and route == "/api/maintainer/review-pack":
        params = parse_qs(parsed.query)
        out_dir = Path(config.workspace) / ((params.get("out_dir") or ["maintainer_review"])[0])
        report = build_maintainer_review_pack(
            out_dir=out_dir,
            root=Path.cwd(),
            dashboard_dir=Path(config.workspace) / ((params.get("dashboard_dir") or ["maintainer_dashboard"])[0]),
            evidence_dir=(params.get("evidence_dir") or ["real_mac_evidence"])[0],
            launch_assets_dir=(params.get("launch_assets_dir") or ["launch_assets"])[0],
            candidate_dir=(params.get("candidate_dir") or ["public_alpha_candidate"])[0],
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "maintainer_review_pack": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/maintainer/dashboard":
        params = parse_qs(parsed.query)
        dashboard_dir = Path(config.workspace) / ((params.get("dashboard_dir") or ["maintainer_dashboard"])[0])
        report = build_maintainer_dashboard(
            root=Path.cwd(),
            dashboard_dir=dashboard_dir,
            evidence_dir=(params.get("evidence_dir") or ["real_mac_evidence"])[0],
            launch_assets_dir=(params.get("launch_assets_dir") or ["launch_assets"])[0],
            candidate_dir=(params.get("candidate_dir") or ["public_alpha_candidate"])[0],
            demo_dir=(params.get("demo_dir") or ["demo_out"])[0],
            bridge_port=config.port,
        )
        return 200, {"status": "ok" if report.status in {"hold", "candidate_review_ready", "blocked_private_core"} else "fail", "maintainer_dashboard": report.to_dict(), "dashboard_html": str(dashboard_dir / "maintainer_dashboard.html"), "private_core_included": False}
    if method == "GET" and route == "/api/real-capture/execution-pack":
        params = parse_qs(parsed.query)
        out_dir = Path(config.workspace) / ((params.get("out_dir") or ["real_capture_execution_pack"])[0])
        report = build_real_capture_execution_pack(
            out_dir=out_dir,
            duration_ms=int((params.get("duration_ms") or [3000])[0]),
            device_id=(params.get("device_id") or ["microphone:default"])[0],
            sample_rate_hz=int((params.get("sample_rate") or [16000])[0]),
            channels=int((params.get("channels") or [1])[0]),
            chunk_ms=int((params.get("chunk_ms") or [250])[0]),
            mic_dir=(params.get("mic_dir") or ["mic_alpha_live"])[0],
            minutes_dir=(params.get("minutes_dir") or ["mic_minutes_live"])[0],
            asr_minutes_dir=(params.get("asr_minutes_dir") or ["asr_minutes_live"])[0],
            provider=(params.get("provider") or ["sidecar"])[0],
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "real_capture_execution_pack": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/real-capture/execution-gate":
        params = parse_qs(parsed.query)
        mic_dir = Path(config.workspace) / ((params.get("mic_dir") or ["microphone_alpha"])[0])
        minutes_dir_value = (params.get("minutes_dir") or [None])[0]
        asr_dir_value = (params.get("asr_minutes_dir") or [None])[0]
        minutes_dir = Path(config.workspace) / minutes_dir_value if minutes_dir_value else Path(config.workspace) / "bridge_runs" / "ui_mic_minutes" / "microphone_minutes"
        asr_minutes_dir = Path(config.workspace) / asr_dir_value if asr_dir_value else Path(config.workspace) / "bridge_runs" / "ui_asr_minutes" / "asr_minutes"
        report = evaluate_real_capture_execution(
            mic_dir=mic_dir,
            minutes_dir=minutes_dir,
            asr_minutes_dir=asr_minutes_dir,
            require_live_artifacts=(params.get("allow_dry_run") or ["false"])[0].lower() not in {"1", "true", "yes"},
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "real_capture_execution_gate": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/local-asr/smoke-pack":
        params = parse_qs(parsed.query)
        out_dir = Path(config.workspace) / ((params.get("out_dir") or ["local_asr_smoke_pack"])[0])
        report = build_local_asr_smoke_pack(
            out_dir=out_dir,
            audio_path=str(_default_post_capture_audio(config)),
            sidecar_path=str(_default_post_capture_sidecar(config) or Path(config.workspace) / "audio.transcript.txt"),
            reference_path=str(_default_post_capture_sidecar(config) or Path(config.workspace) / "audio.transcript.txt"),
            model_size=(params.get("model_size") or ["small"])[0],
            device=(params.get("device") or ["cpu"])[0],
            smoke_dir=(params.get("smoke_dir") or ["local_asr_smoke"])[0],
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "local_asr_smoke_pack": report.to_dict(), "private_core_included": False}

    if method in {"GET", "POST"} and route == "/api/local-asr/smoke-run":
        params = parse_qs(parsed.query)
        run_id = _safe_run_id(str(payload.get("run_id") or (params.get("run_id") or ["ui_local_asr_smoke"])[0]))
        out_dir = Path(config.workspace) / "bridge_runs" / run_id / "local_asr_smoke"
        audio_path = Path(payload["audio_path"]) if payload.get("audio_path") else _default_post_capture_audio(config)
        sidecar = Path(payload["sidecar"]) if payload.get("sidecar") else _default_post_capture_sidecar(config)
        reference = Path(payload["reference"]) if payload.get("reference") else sidecar
        report = run_local_asr_smoke(
            audio_path=audio_path,
            out_dir=out_dir,
            sidecar_path=sidecar,
            reference_path=reference,
            mode=str(payload.get("mode", (params.get("mode") or ["sidecar"])[0])),
            model_size=str(payload.get("model_size", (params.get("model_size") or ["small"])[0])),
            device=str(payload.get("device", (params.get("device") or ["cpu"])[0])),
            compute_type=str(payload.get("compute_type", "int8")),
            require_real_asr=bool(payload.get("require_real_asr", False)),
            real_asr_report=payload.get("real_asr_report"),
        )
        workflow = {
            "id": "local-asr-smoke",
            "status": "pass" if report.status in {"pass", "warn"} else "fail",
            "score": report.score,
            "run_id": run_id,
            "mode": report.mode,
            "steps": [check.to_dict() for check in report.checks],
            "artifacts": _relative_artifacts(Path(config.workspace), report.artifacts),
            "metrics": report.metrics,
            "summary": report.summary,
            "next_actions": [report.recommendation],
            "local_asr_smoke": report.to_dict(),
            "private_core_included": False,
            "public_core_only": True,
        }
        _workflow_manifest_path(config).write_text(json.dumps({"status": "ok", "workflow": workflow}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 200, {"status": "ok" if workflow["status"] in {"pass", "warn"} else "fail", "request": payload, "workflow": workflow, "local_asr_smoke": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/local-asr/smoke-gate":
        params = parse_qs(parsed.query)
        smoke_dir = Path(config.workspace) / ((params.get("smoke_dir") or ["bridge_runs/ui_local_asr_smoke/local_asr_smoke"])[0])
        real_asr_raw = (params.get("real_asr_dir") or [None])[0]
        real_asr_dir = Path(config.workspace) / real_asr_raw if real_asr_raw else None
        report = evaluate_local_asr_smoke_gate(
            smoke_dir=smoke_dir,
            real_asr_dir=real_asr_dir,
            require_real_asr=(params.get("require_real_asr") or ["false"])[0].lower() in {"1", "true", "yes"},
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "local_asr_smoke_gate": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/launch/assets-pack":
        params = parse_qs(parsed.query)
        out_dir = Path(config.workspace) / ((params.get("out_dir") or ["launch_assets"])[0])
        report = build_launch_asset_pack(
            out_dir=out_dir,
            root=Path.cwd(),
            demo_dir=(params.get("demo_dir") or ["demo_out"])[0],
            bridge_url=f"http://{config.host}:{config.port}",
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "launch_assets_pack": report.to_dict(), "private_core_included": False}

    if method == "GET" and route in {"/api/launch/assets-gate", "/api/launch/polish-check"}:
        params = parse_qs(parsed.query)
        assets_raw = (params.get("assets_dir") or [None])[0]
        assets_dir = Path(config.workspace) / assets_raw if assets_raw else Path(config.workspace) / "launch_assets"
        report = run_launch_polish_check(
            root=Path.cwd(),
            launch_assets_dir=assets_dir,
            demo_dir=(params.get("demo_dir") or ["demo_out"])[0],
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "launch_polish_check": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/evidence/real-mac-pack":
        params = parse_qs(parsed.query)
        out_dir = Path(config.workspace) / ((params.get("out_dir") or ["real_mac_evidence_pack"])[0])
        report = build_real_mac_evidence_pack(
            out_dir=out_dir,
            root=Path.cwd(),
            duration_ms=int((params.get("duration_ms") or [3000])[0]),
            mic_dir=(params.get("mic_dir") or ["mic_alpha_live"])[0],
            minutes_dir=(params.get("minutes_dir") or ["mic_minutes_live"])[0],
            asr_minutes_dir=(params.get("asr_minutes_dir") or ["asr_minutes_faster_whisper"])[0],
            local_asr_dir=(params.get("local_asr_dir") or ["local_asr_smoke"])[0],
            launch_assets_dir=(params.get("launch_assets_dir") or ["launch_assets"])[0],
            evidence_dir=(params.get("evidence_dir") or ["real_mac_evidence"])[0],
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "real_mac_evidence_pack": report.to_dict(), "private_core_included": False}

    if method in {"GET", "POST"} and route == "/api/evidence/real-mac-collect":
        params = parse_qs(parsed.query)
        report = collect_real_mac_evidence(
            root=Path.cwd(),
            evidence_dir=Path(config.workspace) / ((params.get("evidence_dir") or ["real_mac_evidence"])[0]),
            mic_dir=(params.get("mic_dir") or ["mic_alpha_live"])[0],
            minutes_dir=(params.get("minutes_dir") or ["mic_minutes_live"])[0],
            asr_minutes_dir=(params.get("asr_minutes_dir") or ["asr_minutes_faster_whisper"])[0],
            local_asr_dir=(params.get("local_asr_dir") or ["local_asr_smoke"])[0],
            launch_assets_dir=(params.get("launch_assets_dir") or ["launch_assets"])[0],
            copy_artifacts=True,
        )
        workflow = {
            "id": "real-mac-evidence-collect",
            "status": "pass" if report.status == "pass" else "warn",
            "score": report.score,
            "steps": [check.to_dict() for check in report.checks],
            "artifacts": _relative_artifacts(Path(config.workspace), report.artifacts),
            "summary": report.summary,
            "next_actions": [report.recommendation],
            "real_mac_evidence": report.to_dict(),
            "private_core_included": False,
            "public_core_only": True,
        }
        _workflow_manifest_path(config).write_text(json.dumps({"status": "ok", "workflow": workflow}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "workflow": workflow, "real_mac_evidence": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/evidence/export-pack":
        params = parse_qs(parsed.query)
        out_dir = Path(config.workspace) / ((params.get("out_dir") or ["evidence_export_pack"])[0])
        report = build_evidence_export_pack(
            out_dir=out_dir,
            root=Path.cwd(),
            export_dir=Path(config.workspace) / ((params.get("export_dir") or ["evidence_export"])[0]),
            demo_dir=(params.get("demo_dir") or ["demo_out"])[0],
            evidence_dir=(params.get("evidence_dir") or ["real_mac_evidence"])[0],
            launch_assets_dir=(params.get("launch_assets_dir") or ["launch_assets"])[0],
            dashboard_dir=(params.get("dashboard_dir") or ["maintainer_dashboard"])[0],
            screenshot_dir=Path(config.workspace) / ((params.get("screenshot_dir") or ["screenshots"])[0]),
            bridge_url=f"http://{config.host}:{config.port}",
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "evidence_export_pack": report.to_dict(), "private_core_included": False}

    if method in {"GET", "POST"} and route == "/api/evidence/export-run":
        params = parse_qs(parsed.query)
        out_dir = Path(config.workspace) / str(payload.get("out_dir") or (params.get("out_dir") or ["evidence_export"])[0])
        report = export_evidence_bundle(
            root=Path.cwd(),
            out_dir=out_dir,
            demo_dir=str(payload.get("demo_dir") or (params.get("demo_dir") or ["demo_out"])[0]),
            evidence_dir=str(payload.get("evidence_dir") or (params.get("evidence_dir") or ["real_mac_evidence"])[0]),
            launch_assets_dir=str(payload.get("launch_assets_dir") or (params.get("launch_assets_dir") or ["launch_assets"])[0]),
            dashboard_dir=str(payload.get("dashboard_dir") or (params.get("dashboard_dir") or ["maintainer_dashboard"])[0]),
            screenshot_dir=Path(config.workspace) / str(payload.get("screenshot_dir") or (params.get("screenshot_dir") or ["screenshots"])[0]),
            copy_artifacts=not bool(payload.get("no_copy_artifacts")),
        )
        workflow = {"id": "evidence-export-run", "status": report.status, "score": report.score, "steps": [check.to_dict() for check in report.checks], "artifacts": _relative_artifacts(Path(config.workspace), report.artifacts), "summary": report.summary, "next_actions": [report.recommendation], "evidence_export": report.to_dict(), "private_core_included": False, "public_core_only": True}
        _workflow_manifest_path(config).write_text(json.dumps({"status": "ok", "workflow": workflow}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "workflow": workflow, "evidence_export": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/evidence/export-gate":
        params = parse_qs(parsed.query)
        report = run_evidence_export_gate(
            root=Path.cwd(),
            export_dir=Path(config.workspace) / ((params.get("export_dir") or ["evidence_export"])[0]),
            screenshot_dir=Path(config.workspace) / ((params.get("screenshot_dir") or ["screenshots"])[0]),
            min_screenshots=int((params.get("min_screenshots") or [3])[0]),
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "evidence_export_gate": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/screenshots/automation-pack":
        params = parse_qs(parsed.query)
        out_dir = Path(config.workspace) / ((params.get("out_dir") or ["screenshot_automation"])[0])
        report = build_screenshot_automation_pack(
            out_dir=out_dir,
            root=Path.cwd(),
            demo_dir=(params.get("demo_dir") or ["demo_out"])[0],
            screenshot_dir=Path(config.workspace) / ((params.get("screenshot_dir") or ["screenshots"])[0]),
            bridge_url=f"http://{config.host}:{config.port}",
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "screenshot_automation_pack": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/screenshots/readiness-gate":
        params = parse_qs(parsed.query)
        report = run_screenshot_readiness_gate(
            root=Path.cwd(),
            screenshot_dir=Path(config.workspace) / ((params.get("screenshot_dir") or ["screenshots"])[0]),
            demo_dir=(params.get("demo_dir") or ["demo_out"])[0],
            min_screenshots=int((params.get("min_screenshots") or [3])[0]),
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "screenshot_readiness": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/capture/plan":
        params = parse_qs(parsed.query)
        plan = build_live_capture_plan(
            out_dir=(params.get("out_dir") or ["mic_alpha_live"])[0],
            duration_ms=int((params.get("duration_ms") or [3000])[0]),
            device_id=(params.get("device_id") or ["microphone:default"])[0],
            sample_rate_hz=int((params.get("sample_rate") or [16000])[0]),
            channels=int((params.get("channels") or [1])[0]),
        )
        return 200, {"status": "ok", "capture_plan": plan.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/capture/validation-pack":
        params = parse_qs(parsed.query)
        out_dir = Path(config.workspace) / ((params.get("out_dir") or ["capture_validation_pack"])[0])
        report = build_capture_validation_pack(
            out_dir=out_dir,
            duration_ms=int((params.get("duration_ms") or [3000])[0]),
            device_id=(params.get("device_id") or ["microphone:default"])[0],
            sample_rate_hz=int((params.get("sample_rate") or [16000])[0]),
            channels=int((params.get("channels") or [1])[0]),
            chunk_ms=int((params.get("chunk_ms") or [250])[0]),
            mic_dir=(params.get("mic_dir") or ["mic_alpha_live"])[0],
            minutes_dir=(params.get("minutes_dir") or ["mic_minutes_live"])[0],
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "capture_validation_pack": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/capture/validation-run":
        params = parse_qs(parsed.query)
        mic_dir = Path(config.workspace) / ((params.get("mic_dir") or ["microphone_alpha"])[0])
        minutes_dir_raw = (params.get("minutes_dir") or [None])[0]
        minutes_dir = Path(config.workspace) / minutes_dir_raw if minutes_dir_raw else None
        report = evaluate_capture_validation_run(mic_dir=mic_dir, minutes_dir=minutes_dir, provider=(params.get("provider") or ["sidecar"])[0])
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "capture_validation_run": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/asr/validation-pack":
        params = parse_qs(parsed.query)
        out_dir = Path(config.workspace) / ((params.get("out_dir") or ["asr_validation_pack"])[0])
        report = build_asr_validation_pack(
            out_dir=out_dir,
            audio_path=str(_default_post_capture_audio(config)),
            provider=(params.get("provider") or ["sidecar"])[0],
            sidecar_path=str(_default_post_capture_sidecar(config) or Path(config.workspace) / "audio.transcript.txt"),
            reference_path=str(_default_post_capture_sidecar(config) or Path(config.workspace) / "audio.transcript.txt"),
            model_size=(params.get("model_size") or ["small"])[0],
            device=(params.get("device") or ["cpu"])[0],
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "asr_validation_pack": report.to_dict(), "private_core_included": False}

    if method in {"GET", "POST"} and route == "/api/asr/validation-run":
        params = parse_qs(parsed.query)
        provider = payload.get("provider") or (params.get("provider") or ["sidecar"])[0]
        run_id = _safe_run_id(str(payload.get("run_id") or (params.get("run_id") or ["ui_asr_validation"])[0]))
        out_dir = Path(config.workspace) / "bridge_runs" / run_id / "asr_validation"
        audio_path = Path(payload["audio_path"]) if payload.get("audio_path") else _default_post_capture_audio(config)
        sidecar = Path(payload["sidecar"]) if payload.get("sidecar") else _default_post_capture_sidecar(config)
        reference = Path(payload["reference"]) if payload.get("reference") else sidecar
        report = run_asr_validation(
            audio_path=audio_path,
            out_dir=out_dir,
            provider=str(provider),
            sidecar_path=sidecar,
            reference_path=reference,
            meeting_id=str(payload.get("meeting_id", f"mtg_bridge_asr_{run_id}")),
            title=str(payload.get("title", "AI Meeting Agent ASR Validation")),
            model_size=str(payload.get("model_size", (params.get("model_size") or ["small"])[0])),
            device=str(payload.get("device", (params.get("device") or ["cpu"])[0])),
            compute_type=str(payload.get("compute_type", "int8")),
            dry_run=bool(payload.get("dry_run", False)),
        )
        workflow = {
            "id": "asr-validation",
            "status": "pass" if report.status in {"pass", "warn"} else "fail",
            "score": report.score,
            "run_id": run_id,
            "provider": report.provider,
            "steps": [check.to_dict() for check in report.checks],
            "artifacts": _relative_artifacts(Path(config.workspace), report.artifacts),
            "metrics": report.metrics,
            "summary": report.summary,
            "next_actions": [report.recommendation],
            "asr_validation": report.to_dict(),
            "private_core_included": False,
            "public_core_only": True,
        }
        _workflow_manifest_path(config).write_text(json.dumps({"status": "ok", "workflow": workflow}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 200, {"status": "ok" if workflow["status"] in {"pass", "warn"} else "fail", "request": payload, "workflow": workflow, "asr_validation": report.to_dict(), "private_core_included": False}

    if method in {"GET", "POST"} and route in {"/api/workflows/asr-to-minutes", "/api/asr/to-minutes"}:
        params = parse_qs(parsed.query)
        provider = payload.get("provider") or (params.get("provider") or ["sidecar"])[0]
        run_id = _safe_run_id(str(payload.get("run_id") or (params.get("run_id") or ["ui_asr_minutes"])[0]))
        out_dir = Path(config.workspace) / "bridge_runs" / run_id / "asr_minutes"
        audio_path = Path(payload["audio_path"]) if payload.get("audio_path") else _default_post_capture_audio(config)
        sidecar = Path(payload["sidecar"]) if payload.get("sidecar") else _default_post_capture_sidecar(config)
        reference = Path(payload["reference"]) if payload.get("reference") else sidecar
        report = run_asr_to_minutes_workflow(
            audio_path=audio_path,
            out_dir=out_dir,
            provider=str(provider),
            sidecar_path=sidecar,
            reference_path=reference,
            meeting_id=str(payload.get("meeting_id", f"mtg_bridge_asr_minutes_{run_id}")),
            title=str(payload.get("title", "AI Meeting Agent ASR to Minutes")),
            model_size=str(payload.get("model_size", (params.get("model_size") or ["small"])[0])),
            device=str(payload.get("device", (params.get("device") or ["cpu"])[0])),
            compute_type=str(payload.get("compute_type", "int8")),
            dry_run=bool(payload.get("dry_run", False)),
        )
        workflow = {
            "id": "asr-to-minutes",
            "status": "pass" if report.status in {"pass", "warn"} else "fail",
            "score": report.score,
            "run_id": run_id,
            "provider": report.provider,
            "steps": [check.to_dict() for check in report.checks],
            "artifacts": _relative_artifacts(Path(config.workspace), report.artifacts),
            "metrics": report.metrics,
            "summary": report.summary,
            "next_actions": [report.recommendation],
            "asr_minutes": report.to_dict(),
            "private_core_included": False,
            "public_core_only": True,
        }
        _workflow_manifest_path(config).write_text(json.dumps({"status": "ok", "workflow": workflow}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 200, {"status": "ok" if workflow["status"] in {"pass", "warn"} else "fail", "request": payload, "workflow": workflow, "asr_minutes": report.to_dict(), "private_core_included": False}

    if method == "GET" and route == "/api/post-capture/gate":
        params = parse_qs(parsed.query)
        audio_path = (params.get("audio_path") or [None])[0]
        sidecar = (params.get("sidecar") or [None])[0]
        provider = (params.get("provider") or ["sidecar"])[0]
        report = evaluate_post_capture_gate(
            Path(config.workspace),
            audio_path=Path(audio_path) if audio_path else _default_post_capture_audio(config),
            provider=provider,
            sidecar_path=Path(sidecar) if sidecar else _default_post_capture_sidecar(config),
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "post_capture_gate": report.to_dict(), "private_core_included": False}

    if route == "/api/recording/safety-gate" and method in {"GET", "POST"}:
        params = parse_qs(parsed.query)
        live_requested = bool(payload.get("live_requested") or payload.get("real_capture")) if method == "POST" else (params.get("live") or ["false"])[0].lower() in {"1", "true", "yes"}
        confirmation = payload.get("confirmation") or (LIVE_CONFIRMATION_PHRASE if payload.get("confirm_live_recording") or payload.get("confirm_real_capture") else None)
        report = evaluate_recording_safety_gate(
            live_requested=live_requested,
            confirmation=confirmation,
            notice_acknowledged=bool(payload.get("notice_acknowledged")),
            participants_notified=bool(payload.get("participants_notified")),
            duration_ms=int(payload.get("duration_ms", (params.get("duration_ms") or [3000])[0])),
            publication_hold=True,
        )
        return 200, {"status": "ok" if report.status in {"pass", "warn"} else "fail", "recording_safety_gate": report.to_dict(), "private_core_included": False}
    if method == "GET" and route in {"/api/microphone/doctor", "/api/microphone/preflight"}:
        params = parse_qs(parsed.query)
        report = run_microphone_alpha_doctor(
            device_id=(params.get("device_id") or ["microphone:default"])[0],
            sample_rate_hz=int((params.get("sample_rate") or [16000])[0]),
            channels=int((params.get("channels") or [1])[0]),
            chunk_ms=int((params.get("chunk_ms") or [250])[0]),
            duration_ms=int((params.get("duration_ms") or [3000])[0]),
            require_sounddevice=(params.get("require_sounddevice") or ["false"])[0].lower() in {"1", "true", "yes"},
        )
        response = {"status": "ok" if report.status in {"pass", "warn"} else "fail", "microphone": report.to_dict()}
        if route == "/api/microphone/preflight":
            response["preflight"] = report.to_dict()
        return 200, response
    if method == "GET" and route == "/api/manifest":
        manifest = Path(config.workspace) / "desktop_alpha_manifest.json"
        if manifest.exists():
            return 200, json.loads(manifest.read_text(encoding="utf-8"))
        return 404, {"status": "missing", "path": str(manifest), "private_core_included": False}
    if method == "GET" and route in {"/api/workflows/last", "/api/workflows/latest"}:
        return 200, _read_last_workflow(config) or {"status": "empty", "workflow": None, "private_core_included": False}
    if method == "POST" and route in {"/api/workflows/microphone-to-minutes", "/api/microphone/to-minutes"}:
        workflow = _run_microphone_to_minutes_bridge_workflow(config, payload)
        return 200, {"status": "ok" if workflow["status"] in {"pass", "warn"} else "fail", "request": payload, "workflow": workflow, "private_core_included": False}

    if method == "POST" and route in {"/api/workflows/microphone-alpha", "/api/workflows/microphone-dry-run", "/api/microphone/alpha"}:
        real_capture = bool(payload.get("real_capture"))
        duration_ms = int(payload.get("duration_ms", 3000))
        device_id = str(payload.get("device_id", "microphone:default"))
        report = run_microphone_alpha_recording(
            out_dir=Path(config.workspace) / "microphone_alpha",
            session_id=str(payload.get("session_id", "ui_mic_alpha")),
            device_id=device_id,
            duration_ms=duration_ms,
            sample_rate_hz=int(payload.get("sample_rate_hz", 16000)),
            channels=int(payload.get("channels", 1)),
            chunk_ms=int(payload.get("chunk_ms", 250)),
            dry_run=not real_capture,
            confirm_live_recording=payload.get("confirmation") or (LIVE_CONFIRMATION_PHRASE if payload.get("confirm_real_capture") or payload.get("confirm_live_recording") else None),
            notice_acknowledged=bool(payload.get("notice_acknowledged")),
            participants_notified=bool(payload.get("participants_notified")),
            actor_id=str(payload.get("actor_id", "desktop_bridge_user")),
        )
        workflow = {
            "id": "microphone-alpha-dry-run" if not real_capture else "microphone-alpha-real-capture",
            "status": "pass" if report.status in {"pass", "warn"} else "fail",
            "score": report.score,
            "workspace": str(config.workspace),
            "private_core_included": False,
            "mode": report.mode,
            "steps": [check.to_dict() for check in report.checks],
            "artifacts": report.artifacts,
            "next_actions": [report.recommendation],
            "microphone": report.to_dict(),
        }
        latest = Path(config.workspace) / "microphone_alpha_smoke.json"
        latest.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 200, {"status": "ok" if workflow["status"] in {"pass", "warn"} else "fail", "request": payload, "workflow": workflow, "microphone": report.to_dict()}

    if method == "POST" and route in {"/api/workflows/simulated-record", "/api/workflows/simulated-recording", "/api/smoke"}:
        workflow = _run_simulated_recording_workflow(config, payload)
        return 200, {"status": "ok", "request": payload, "workflow": workflow, "private_core_included": False}
    return 404, {"status": "not_found", "method": method, "path": route, "private_core_included": False}


def make_desktop_bridge_handler(config: DesktopBridgeConfig):
    class DesktopBridgeHandler(BaseHTTPRequestHandler):
        _meeting_agent_bridge_handler = True
        server_version = "MeetingAgentDesktopBridge/1.0"
        protocol_version = "HTTP/1.0"

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send_json({"status": "ok"})

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api") or parsed.path == "/health":
                status, payload = handle_bridge_request("GET", parsed.path + (f"?{parsed.query}" if parsed.query else ""), {}, config=config)
                self._send_json(payload, status=status)
                return
            self._serve_static(parsed.path)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            status, payload = handle_bridge_request("POST", parsed.path, self._read_body_json(), config=config)
            self._send_json(payload, status=status)

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _read_body_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            try:
                return json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                return {"raw": raw}

        def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self._send_common_headers()
            self.end_headers()
            self.wfile.write(data)
            self.close_connection = True

        def _send_common_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")

        def _serve_static(self, path: str) -> None:
            if path.startswith("/workspace/"):
                root_dir = Path(config.workspace)
                relative = Path(path[len("/workspace/"):])
            else:
                root_dir = _resolve_static_dir(config)
                relative = Path("index.html") if path in {"", "/", "/index.html", "/app", "/app/"} else Path(path.lstrip("/"))
                if path.startswith("/app/"):
                    relative = Path(path[len("/app/"):])
            root = root_dir.resolve()
            target = (root_dir / relative).resolve()
            if root != target and root not in target.parents:
                self._send_json({"status": "not_found", "path": path}, status=404)
                return
            if not target.exists() or target.is_dir():
                self._send_json({"status": "not_found", "path": path, "static_dir": str(root_dir)}, status=404)
                return
            data = target.read_bytes()
            content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self._send_common_headers()
            self.end_headers()
            self.wfile.write(data)
            self.close_connection = True

    return DesktopBridgeHandler


class DesktopBridgeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    block_on_close = False


def create_desktop_bridge_server(config: DesktopBridgeConfig) -> ThreadingHTTPServer:
    _ensure_workspace(config)
    return DesktopBridgeHTTPServer((config.host, config.port), make_desktop_bridge_handler(config))


def serve_desktop_bridge(config: DesktopBridgeConfig, *, open_browser: bool = False) -> None:
    server = create_desktop_bridge_server(config)
    actual_host, actual_port = server.server_address
    url = f"http://{actual_host}:{actual_port}"
    print(f"Desktop Alpha Bridge: {url}")
    print(f"Workspace: {Path(config.workspace).resolve()}")
    print("UI: open the printed URL, not the file:// path, for live Bridge status.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Desktop Alpha Bridge stopped")
    finally:
        server.server_close()


def serve_bridge(config: BridgeConfig, *, open_browser: bool = False) -> None:
    serve_desktop_bridge(config, open_browser=open_browser)


def start_desktop_bridge_in_thread(config: DesktopBridgeConfig) -> tuple[ThreadingHTTPServer, Thread]:
    server = create_desktop_bridge_server(config)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
