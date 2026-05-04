from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from meeting_agent.core.schemas import MinutesDraft, Transcript, to_dict
from meeting_agent.intelligence.rule_minutes import RuleBasedMinutesGenerator
from meeting_agent.streaming.replay import TranscriptReplaySettings, transcript_replay_payload

ASSET_FILES = ("index.html", "styles.css", "app.js", "bridge_config.js")


def build_desktop_lite_bundle(
    transcript: Transcript,
    out_dir: str | Path,
    *,
    minutes: MinutesDraft | None = None,
    settings: TranscriptReplaySettings | None = None,
    audio_diagnostics: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
    asr_smoke: dict[str, Any] | None = None,
    audio_levels: dict[str, Any] | None = None,
    desktop_alpha: dict[str, Any] | None = None,
    bridge_enabled: bool = False,
    bridge_url: str = "",
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Create a dependency-free Desktop Alpha UI bundle.

    The generated directory can be opened directly in a browser, embedded in
    Electron/Tauri, or served by the local Desktop Bridge. It contains only
    public Community data and never bundles the private quality engine.
    """

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    minutes = minutes or RuleBasedMinutesGenerator().generate(transcript)
    replay = transcript_replay_payload(transcript, settings)

    paths: dict[str, Path] = {}
    for filename in ASSET_FILES:
        destination = out / filename
        text = _read_asset(filename)
        if filename == "bridge_config.js":
            text = _bridge_config(bridge_enabled=bridge_enabled, bridge_url=bridge_url)
        destination.write_text(text, encoding="utf-8")
        paths[filename] = destination

    demo_payload = {
        "transcript": to_dict(transcript),
        "minutes": to_dict(minutes),
        "replay": replay,
        "audio_diagnostics": audio_diagnostics or {},
        "preflight": preflight or {},
        "asr_smoke": asr_smoke or {},
        "audio_levels": audio_levels or {},
        "desktop_alpha": desktop_alpha or {},
    }
    if extra_payload:
        demo_payload.update(extra_payload)
    (out / "demo_data.js").write_text(
        "window.MEETING_AGENT_DEMO = " + json.dumps(demo_payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    (out / "transcript.json").write_text(json.dumps(to_dict(transcript), ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "minutes.json").write_text(json.dumps(to_dict(minutes), ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "replay_events.json").write_text(json.dumps(replay, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "README.md").write_text(_bundle_readme(transcript), encoding="utf-8")

    paths.update(
        {
            "demo_data.js": out / "demo_data.js",
            "transcript.json": out / "transcript.json",
            "minutes.json": out / "minutes.json",
            "replay_events.json": out / "replay_events.json",
            "README.md": out / "README.md",
        }
    )
    return paths


def copy_desktop_lite_assets(out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for filename in ASSET_FILES + ("demo_data.js",):
        destination = out / filename
        destination.write_text(_read_asset(filename), encoding="utf-8")
        paths[filename] = destination
    return paths


def _read_asset(filename: str) -> str:
    # Direct filesystem access is deterministic for source-checkout, zip, and
    # unit-test execution in the Community package. Avoiding importlib.resources
    # here also keeps Desktop Alpha bundle generation free of package-loader quirks.
    return (Path(__file__).resolve().parent / "assets" / filename).read_text(encoding="utf-8")


def _bridge_config(*, bridge_enabled: bool, bridge_url: str) -> str:
    payload = {"enabled": bridge_enabled, "url": bridge_url}
    return "window.MEETING_AGENT_BRIDGE = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n"


def _bundle_readme(transcript: Transcript) -> str:
    return f"""# AI Meeting Agent Desktop Alpha UI Bundle

Open `index.html` in a browser to run the simulated realtime transcript UI.

- Meeting ID: `{transcript.meeting_id}`
- Title: `{transcript.title}`
- Segments: `{len(transcript.segments)}`

To use local workflow APIs, serve this bundle with:

```bash
PYTHONPATH=src python -m meeting_agent desktop-serve --workspace ./desktop_alpha_bundle
```

This bundle is intentionally public-Community safe. It does not include the
production-quality engine, model router, private evaluation data, speaker-name
mapping, or enterprise modules.
"""
