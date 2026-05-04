from __future__ import annotations

import json
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent import __version__


@dataclass(frozen=True)
class DesktopAlphaBundleResult:
    status: str
    out_dir: str
    files: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def create_desktop_alpha_bundle(
    *,
    source_root: str | Path,
    workflow_dir: str | Path,
    out_dir: str | Path,
    app_name: str = "AI Meeting Agent Community Desktop Alpha",
) -> DesktopAlphaBundleResult:
    source = Path(source_root)
    workflow = Path(workflow_dir)
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {}
    notes: list[str] = []
    app_dir = out / "app"
    desktop_lite_alias = out / "desktop_lite"
    artifacts_dir = out / "artifacts"
    scripts_dir = out / "scripts"
    for directory in [app_dir, desktop_lite_alias, artifacts_dir, scripts_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    def rel(path: Path) -> str:
        try:
            return str(path.relative_to(out))
        except ValueError:
            return str(path)

    desktop_lite = workflow / "desktop_lite"
    if not desktop_lite.exists():
        raise FileNotFoundError(f"Desktop Lite bundle was not found: {desktop_lite}")
    shutil.copytree(desktop_lite, app_dir, dirs_exist_ok=True)
    shutil.copytree(desktop_lite, desktop_lite_alias, dirs_exist_ok=True)
    files["app_index"] = rel(app_dir / "index.html")
    files["desktop_lite_index"] = rel(desktop_lite_alias / "index.html")

    artifact_names = [
        "workflow_report.json",
        "workflow_report.md",
        "audio.wav",
        "audio_info.json",
        "audio_diagnostics.json",
        "audio_diagnostics.md",
        "audio_levels.json",
        "audio_levels.md",
        "capture_readiness.json",
        "asr_doctor.json",
        "asr_smoke.json",
        "meeting_from_audio.json",
        "minutes.json",
        "minutes.md",
        "minutes.html",
        "verification.json",
        "quality_gate.json",
        "action_items.csv",
    ]
    for name in artifact_names:
        src = workflow / name
        if src.exists():
            dst = artifacts_dir / name
            shutil.copy2(src, dst)
            files[name] = rel(dst)
        else:
            notes.append(f"Missing optional workflow artifact: {name}")

    launch_sh = scripts_dir / "launch.sh"
    launch_sh.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "DIR=\"$(cd \"$(dirname \"$0\")/..\" && pwd)\"\n"
        "PYTHON_BIN=\"${PYTHON_BIN:-python3}\"\n"
        "echo \"Serving Desktop Alpha at http://127.0.0.1:8765\"\n"
        "cd \"$DIR/app\"\n"
        "exec \"$PYTHON_BIN\" -m http.server 8765 --bind 127.0.0.1\n",
        encoding="utf-8",
    )
    launch_sh.chmod(0o755)
    launch_bat = scripts_dir / "launch.bat"
    launch_bat.write_text(
        "@echo off\r\n"
        "cd /d %~dp0\\..\\app\r\n"
        "echo Serving Desktop Alpha at http://127.0.0.1:8765\r\n"
        "python -m http.server 8765 --bind 127.0.0.1\r\n",
        encoding="utf-8",
    )
    launch_py = out / "launch_desktop_alpha.py"
    launch_py.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "from meeting_agent.desktop.bridge import DesktopBridgeConfig, serve_desktop_bridge\n"
        "workspace = Path(__file__).resolve().parent\n"
        "serve_desktop_bridge(DesktopBridgeConfig(workspace=workspace, static_dir=workspace / 'desktop_lite'))\n",
        encoding="utf-8",
    )
    launch_py.chmod(0o755)
    files["launch_sh"] = rel(launch_sh)
    files["launch_bat"] = rel(launch_bat)
    files["launch_py"] = rel(launch_py)

    manifest = {
        "name": app_name,
        "version": _project_version(source),
        "kind": "portable-desktop-alpha",
        "status": "developer_preview",
        "python": sys.version.split()[0],
        "entrypoint": "app/index.html",
        "bridge_entrypoint": "launch_desktop_alpha.py",
        "scripts": {"posix": "scripts/launch.sh", "windows": "scripts/launch.bat"},
        "artifacts": files,
        "public_boundary": {
            "included": [
                "Desktop Lite UI",
                "local workflow artifacts",
                "simulated audio",
                "sidecar ASR smoke",
                "local bridge launcher",
            ],
            "excluded": [
                "Private Quality Engine",
                "model router",
                "private eval datasets",
                "enterprise admin/billing/SSO",
            ],
        },
    }
    manifest_path = out / "desktop_alpha_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["desktop_alpha_manifest"] = rel(manifest_path)

    readme_path = out / "README.md"
    readme_path.write_text(_readme(app_name, manifest), encoding="utf-8")
    files["README"] = rel(readme_path)
    return DesktopAlphaBundleResult("pass", ".", files, notes)


def build_desktop_alpha_bundle(
    out_dir: str | Path,
    *,
    transcript_path: str | Path | None = None,
    minutes_path: str | Path | None = None,
    bridge_host: str = "127.0.0.1",
    bridge_port: int = 8765,
) -> dict[str, str]:
    """Build a deterministic portable Desktop Alpha bundle for CLI users."""

    out = Path(out_dir)
    workflow_dir = out.parent / f".{out.name}_workflow"
    from meeting_agent.workflows.local_audio import default_sidecar_text, run_local_audio_workflow

    run_local_audio_workflow(
        workflow_dir,
        session_id="desktop_alpha_bundle",
        total_ms=3000,
        chunk_ms=250,
        meeting_id="mtg_desktop_alpha_bundle",
        title="Desktop Alpha Bundle Workflow",
        sidecar_text=default_sidecar_text("v0.7"),
    )
    result = create_desktop_alpha_bundle(source_root=Path.cwd(), workflow_dir=workflow_dir, out_dir=out)
    return result.files


def _project_version(source_root: Path) -> str:
    init_py = source_root / "src" / "meeting_agent" / "__init__.py"
    if init_py.exists():
        for line in init_py.read_text(encoding="utf-8").splitlines():
            if line.startswith("__version__"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return __version__


def _readme(app_name: str, manifest: dict[str, Any]) -> str:
    return f"""# {app_name}

This is a portable Developer Preview bundle for local review.

## Run static UI only

```bash
./scripts/launch.sh
```

Then open `http://127.0.0.1:8765` in your browser.

## Run with local Desktop Bridge

```bash
PYTHONPATH=src python launch_desktop_alpha.py
```

## Included

- Static Desktop Lite UI
- Simulated local audio workflow artifacts
- Audio quality diagnostics
- Audio level frames for the UI meter
- Sidecar ASR smoke transcript
- Evidence-linked minutes outputs

## Intentionally excluded

- Private Quality Engine
- Advanced Japanese correction pipeline
- Model router selection logic
- Private evaluation datasets
- Enterprise admin, billing, SSO, and audit-log implementation

Manifest kind: `{manifest.get('kind')}`  
Status: `{manifest.get('status')}`
"""
