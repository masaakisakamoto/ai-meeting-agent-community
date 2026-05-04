from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent import __version__
from meeting_agent.core.schemas import utc_now_iso


@dataclass(frozen=True)
class LaunchCheck:
    id: str
    status: str
    detail: str
    category: str = "launch"
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LaunchReport:
    status: str
    score: float
    generated_at: str
    version: str
    recommendation: str
    checks: list[LaunchCheck]
    artifacts: dict[str, str] = field(default_factory=dict)
    missing_required: list[str] = field(default_factory=list)
    missing_recommended: list[str] = field(default_factory=list)
    estimated_remaining_work: str = "real microphone evidence, local ASR smoke, screenshots, and maintainer publication approval"
    private_core_included: bool = False

    @property
    def missing_or_warn_items(self) -> list[str]:
        return list(self.missing_required) + list(self.missing_recommended)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        payload["missing_or_warn_items"] = self.missing_or_warn_items
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Launch Readiness / Assets",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Version: `{self.version}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            f"- Generated at: `{self.generated_at}`",
            "",
            "## Recommendation",
            "",
            self.recommendation,
            "",
        ]
        if self.artifacts:
            lines.extend(["## Artifacts", ""])
            for name, path in sorted(self.artifacts.items()):
                lines.append(f"- `{name}`: `{path}`")
            lines.append("")
        lines.extend(["## Checks", "", "| Check | Status | Required | Category | Detail |", "|---|---|---:|---|---|"])
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | `{str(check.required).lower()}` | {check.category} | {_md(check.detail)} |")
        if self.missing_required:
            lines.extend(["", "## Missing required", ""])
            lines.extend(f"- `{item}`" for item in self.missing_required)
        if self.missing_recommended:
            lines.extend(["", "## Missing recommended", ""])
            lines.extend(f"- `{item}`" for item in self.missing_recommended)
        lines.append("")
        return "\n".join(lines)


# Compatibility type aliases used by tests/CLI/Bridge.
LaunchAssetCheck = LaunchCheck
LaunchAssetsReport = LaunchReport
LaunchAssetReport = LaunchReport
LaunchReadinessReport = LaunchReport
LaunchAssetReadinessReport = LaunchReport
LaunchAssetGateReport = LaunchReport

REQUIRED_ASSETS: dict[str, str] = {
    "README_PUBLIC_ALPHA_DRAFT.md": "Expectation-controlled public-alpha README draft",
    "QUICKSTART_MACOS.md": "macOS private-alpha setup and first-run guide",
    "KNOWN_LIMITATIONS.md": "Known limitations and explicit non-goals",
    "DEMO_SCRIPT.md": "Demo script for private review and later launch recording",
    "MAINTAINER_LAUNCH_CHECKLIST.md": "Maintainer-only final launch checklist",
    "PRIVATE_CORE_BOUNDARY_SUMMARY.md": "Open-core / protected-core boundary summary",
}

RECOMMENDED_ASSETS: dict[str, str] = {
    "SCREENSHOT_GUIDE.md": "Screenshot and GIF capture guide",
    "RELEASE_NOTES_DRAFT.md": "Public alpha release notes draft",
    "FAQ_DRAFT.md": "Expectation-control FAQ draft",
    "scripts/verify_private_hold.sh": "Quick shell check that publication remains on hold",
}


def build_launch_assets_pack(*, out_dir: str | Path, root: str | Path = ".", version_label: str | None = None, **kwargs: Any) -> LaunchReport:
    return build_launch_asset_pack(root=root, out_dir=out_dir, version_label=version_label, **kwargs)


def build_launch_asset_pack(*, root: str | Path = ".", out_dir: str | Path = "launch_assets", demo_dir: str | Path = "demo_out", bridge_url: str | None = None, bridge_port: int | None = None, version_label: str | None = None, **_: Any) -> LaunchReport:
    if bridge_url is None:
        bridge_url = f"http://127.0.0.1:{bridge_port or 8765}"
    root_path = Path(root)
    out = Path(out_dir)
    if not out.is_absolute():
        out = root_path / out
    out.mkdir(parents=True, exist_ok=True)
    (out / "scripts").mkdir(exist_ok=True)

    content = {
        "README_PUBLIC_ALPHA_DRAFT.md": _readme_public_alpha_draft(version_label or f"v{__version__}", bridge_url),
        "QUICKSTART_MACOS.md": _quickstart_macos(),
        "KNOWN_LIMITATIONS.md": _known_limitations(),
        "DEMO_SCRIPT.md": _demo_script(bridge_url),
        "MAINTAINER_LAUNCH_CHECKLIST.md": _maintainer_checklist(),
        "PRIVATE_CORE_BOUNDARY_SUMMARY.md": _private_core_boundary(),
        "SCREENSHOT_GUIDE.md": _screenshot_guide(),
        "RELEASE_NOTES_DRAFT.md": _release_notes_draft(),
        "FAQ_DRAFT.md": _faq_draft(),
        "scripts/verify_private_hold.sh": _verify_private_hold_script(),
    }
    for rel, text in content.items():
        path = out / rel
        _write(path, text)
        if rel.endswith(".sh"):
            path.chmod(0o755)

    manifest = {
        "schema_version": "launch-assets/v1",
        "project": "ai-meeting-agent-community",
        "version": __version__,
        "version_label": version_label or f"v{__version__}",
        "stage": "private_developer_preview",
        "publication_policy": "hold",
        "bridge_url": bridge_url,
        "demo_dir": str(demo_dir),
        "required_assets": list(REQUIRED_ASSETS.keys()),
        "recommended_assets": list(RECOMMENDED_ASSETS.keys()),
        "private_core_included": False,
        "generated_at": utc_now_iso(),
    }
    _write(out / "launch_assets_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _write(out / "launch_asset_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    checks = _asset_checks(out)
    artifacts = {str(p.relative_to(out)): str(p) for p in sorted(out.rglob("*")) if p.is_file()}
    report = LaunchReport(
        status="pass" if all(c.status == "pass" for c in checks if c.required) else "warn",
        score=_score(checks),
        generated_at=utc_now_iso(),
        version=__version__,
        recommendation="Launch asset pack generated for private review. Keep publication-gate on hold until live capture, local ASR evidence, screenshots, and maintainer approval are complete.",
        checks=checks,
        artifacts=artifacts,
        missing_required=[c.id for c in checks if c.required and c.status != "pass"],
        missing_recommended=[c.id for c in checks if not c.required and c.status != "pass"],
        private_core_included=False,
    )
    _write(out / "launch_assets_pack.json", report.to_json() + "\n")
    _write(out / "launch_assets_pack.md", report.to_markdown())
    _write(out / "launch_asset_pack.json", report.to_json() + "\n")
    _write(out / "launch_asset_pack.md", report.to_markdown())
    return report


def run_launch_readiness_gate(*, root: str | Path = ".", launch_assets_dir: str | Path | None = None, assets_dir: str | Path | None = None, demo_dir: str | Path = "demo_out", **kwargs: Any) -> LaunchReport:
    return run_launch_polish_check(root=root, launch_assets_dir=launch_assets_dir or assets_dir, demo_dir=demo_dir, **kwargs)


def run_launch_readiness(*, root: str | Path = ".", bridge_port: int = 8765, **kwargs: Any) -> LaunchReport:
    return run_launch_polish_check(root=root, **kwargs)


def run_launch_asset_readiness(*, root: str | Path = ".", asset_dir: str | Path | None = None) -> LaunchReport:
    return run_launch_polish_check(root=root, launch_assets_dir=asset_dir)


def evaluate_launch_asset_gate(*, root: str | Path = ".", assets_dir: str | Path | None = None, launch_assets_dir: str | Path | None = None, demo_dir: str | Path = "demo_out", **kwargs: Any) -> LaunchReport:
    return run_launch_polish_check(root=root, launch_assets_dir=launch_assets_dir or assets_dir, demo_dir=demo_dir, **kwargs)


def run_launch_polish_check(*, root: str | Path = ".", demo_dir: str | Path = "demo_out", launch_assets_dir: str | Path | None = "launch_assets", **_: Any) -> LaunchReport:
    root_path = Path(root)
    demo = Path(demo_dir)
    if not demo.is_absolute():
        demo = root_path / demo
    assets = _resolve_asset_dir(root_path, launch_assets_dir)
    checks: list[LaunchCheck] = []

    for rel, detail in REQUIRED_ASSETS.items():
        path = assets / rel if assets else None
        checks.append(LaunchCheck(f"asset:{rel}", "pass" if path and path.exists() else "warn", detail if path and path.exists() else f"Missing required launch asset: {rel}", "launch_assets", True, {"path": str(path) if path else None}))
    for rel, detail in RECOMMENDED_ASSETS.items():
        path = assets / rel if assets else None
        checks.append(LaunchCheck(f"asset:{rel}", "pass" if path and path.exists() else "warn", detail if path and path.exists() else f"Missing recommended launch asset: {rel}", "launch_assets", False, {"path": str(path) if path else None}))

    readme = root_path / "README.md"
    readme_text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    checks.append(LaunchCheck("root_readme_expectation_control", "pass" if _contains_any(readme_text, ["Private Developer Preview", "Developer Preview", "Desktop Alpha", "publication-gate"]) else "warn", "Root README contains preview-stage expectation control." if readme_text else "Root README missing.", "repository", True, {"path": str(readme)}))

    for rel in ["desktop_alpha/app/index.html", "minutes.html", "publication_gate.md", "public_alpha_readiness.md"]:
        path = demo / rel
        checks.append(LaunchCheck(f"demo:{rel}", "pass" if path.exists() else "warn", f"Demo artifact {rel} {'present' if path.exists() else 'missing'}.", "demo", False, {"path": str(path)}))

    screenshots = [root_path / "screenshots", root_path / "docs" / "images", demo / "screenshots"]
    has_shots = any(path.exists() and any(path.iterdir()) for path in screenshots)
    checks.append(LaunchCheck("screenshots_curated", "pass" if has_shots else "warn", "Curated screenshots are present." if has_shots else "Curated screenshots are not present yet; capture them before public announcement.", "launch_assets", False, {"candidates": [str(p) for p in screenshots]}))

    policy = root_path / "configs" / "publication_policy.json"
    checks.append(LaunchCheck("publication_hold_policy", "pass" if policy.exists() else "warn", "Publication policy exists and should remain hold." if policy.exists() else "Publication policy missing.", "commercial_guardrail", True, {"path": str(policy)}))

    private_hits = _scan_private_core_dirs(root_path)
    checks.append(LaunchCheck("private_core_excluded", "pass" if not private_hits else "fail", "No private-core directories detected." if not private_hits else f"Private-looking directories detected: {private_hits}", "commercial_guardrail", True, {"hits": private_hits}))

    missing_required = [c.id for c in checks if c.required and c.status != "pass"]
    missing_recommended = [c.id for c in checks if not c.required and c.status != "pass"]
    status = "pass" if not missing_required else "warn"
    if any(c.status == "fail" for c in checks):
        status = "fail"
    return LaunchReport(
        status=status,
        score=_score(checks),
        generated_at=utc_now_iso(),
        version=__version__,
        recommendation=_polish_recommendation(status, missing_required, missing_recommended),
        checks=checks,
        artifacts={},
        missing_required=missing_required,
        missing_recommended=missing_recommended,
        private_core_included=bool(private_hits),
    )


def write_launch_assets_report(report: LaunchReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    _write_report(report, out_json=out_json, out_md=out_md)


def write_launch_asset_pack_report(report: LaunchReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    _write_report(report, out_json=out_json, out_md=out_md)


def write_launch_readiness_report(report: LaunchReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    _write_report(report, out_json=out_json, out_md=out_md)


def write_launch_asset_readiness_report(report: LaunchReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    _write_report(report, out_json=out_json, out_md=out_md)


def write_launch_asset_gate_report(report: LaunchReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    _write_report(report, out_json=out_json, out_md=out_md)


def write_launch_polish_report(report: LaunchReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    _write_report(report, out_json=out_json, out_md=out_md)


def _write_report(report: LaunchReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(report.to_markdown(), encoding="utf-8")


def _asset_checks(out: Path) -> list[LaunchCheck]:
    checks: list[LaunchCheck] = []
    for rel, detail in REQUIRED_ASSETS.items():
        path = out / rel
        checks.append(LaunchCheck(rel, "pass" if path.exists() else "warn", detail if path.exists() else f"Missing required launch asset: {rel}", "launch_assets", True, {"path": str(path)}))
    for rel, detail in RECOMMENDED_ASSETS.items():
        path = out / rel
        checks.append(LaunchCheck(rel, "pass" if path.exists() else "warn", detail if path.exists() else f"Missing recommended launch asset: {rel}", "launch_assets", False, {"path": str(path)}))
    return checks


def _score(checks: list[LaunchCheck]) -> float:
    score = 1.0
    for c in checks:
        if c.status == "fail":
            score -= 0.25 if c.required else 0.1
        elif c.status != "pass":
            score -= 0.12 if c.required else 0.04
    return round(max(score, 0.0), 3)


def _resolve_asset_dir(root: Path, asset_dir: str | Path | None) -> Path | None:
    candidates: list[Path] = []
    if asset_dir:
        path = Path(asset_dir)
        candidates.append(path if path.is_absolute() else root / path)
    candidates.extend([root / "launch_assets", root / "demo_out" / "launch_assets", root / "public_alpha_assets"])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def _scan_private_core_dirs(root: Path) -> list[str]:
    hits: list[str] = []
    for rel in ["private_core", "commercial_core", "quality_engine_private", "enterprise_private", "private_evals"]:
        if (root / rel).exists():
            hits.append(rel)
    return hits


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(n in text for n in needles)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _md(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _polish_recommendation(status: str, missing_required: list[str], missing_recommended: list[str]) -> str:
    if status == "pass":
        if missing_recommended:
            return "Required launch polish is ready for private review. Recommended items remain: " + ", ".join(missing_recommended[:8])
        return "Launch polish is structurally ready for private review. Publication remains blocked until maintainer flips policy after real capture and local ASR evidence pass."
    if status == "fail":
        return "Do not publish. Private-core guardrail failed or launch assets are unsafe."
    return "Keep private. Required launch polish blockers remain: " + ", ".join(missing_required[:8])


def _readme_public_alpha_draft(version_label: str, bridge_url: str) -> str:
    return f"""# AI Meeting Agent Community — Public Alpha Draft

> **Private draft. Do not publish yet.** Publication remains blocked by `publication-gate` until maintainer approval.

AI Meeting Agent Community is a local-first, evidence-linked meeting-intelligence platform prototype. It includes a Desktop Alpha UI, local bridge APIs, simulated audio workflows, post-capture minutes workflows, ASR validation, local ASR smoke scaffolding, and launch-readiness gates.

## Status

- Version: `{version_label}`
- Bridge URL during demo: `{bridge_url}`
- Stage: `Private Developer Preview`
- Public repository: `blocked`
- Public announcement: `blocked`
- Private core included: `false`

## What works today

- Evidence-linked Japanese meeting minutes from deterministic sample transcripts
- Desktop Alpha UI with local bridge controls
- Audio diagnostics, level reports, and safety gates
- Microphone capture validation packs and execution gates
- ASR validation, ASR→minutes, and local ASR smoke scaffolding

## Not ready yet

- Real Mac microphone capture has been validated on one maintainer Mac, but broader hardware coverage is not yet complete
- faster-whisper smoke has been validated on captured audio for the Public Alpha Candidate
- Native installer packaging is not yet complete
"""


def _quickstart_macos() -> str:
    return """# Quickstart for macOS Public Alpha Candidate

> Public Alpha Candidate. Publication remains blocked until maintainer approval.

```bash
git clone <repository-url> ai-meeting-agent-community
cd ai-meeting-agent-community
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m meeting_agent demo --out-dir demo_out
PYTHONPATH=src python3 -m meeting_agent desktop-bridge --workspace demo_out/desktop_alpha --port 8765 --open-browser
```

For audio dependencies, prefer Python 3.12:

```bash
python3.12 -m venv "$HOME/.venvs/ai-meeting-agent-312"
source "$HOME/.venvs/ai-meeting-agent-312/bin/activate"
python -m pip install -U pip
python -m pip install -e ".[audio,asr]"
```
"""


def _known_limitations() -> str:
    return """# Known Limitations

- This is a Public Alpha Candidate, not production-ready.
- Publication is intentionally blocked.
- Real microphone capture has been validated on one maintainer Mac; other environments may require additional validation.
- PC/system audio loopback is not implemented.
- faster-whisper is optional and may require model downloads and local compute.
- The Community generator is deterministic/basic; high-quality Japanese correction and advanced verifier logic remain protected-core candidates.
- Desktop Alpha is not a signed native installer.
"""


def _demo_script(bridge_url: str) -> str:
    return f"""# Demo Script

1. Start bridge: `{bridge_url}`.
2. Show `Bridge Connected`.
3. Run `Simulated Recording`.
4. Show evidence-linked minutes.
5. Run `Local ASR Smoke` with sidecar.
6. Show `Public Alpha Gate = hold` and `Private core included = false`.
7. Explain that real microphone and faster-whisper validation are the remaining public-alpha blockers.
"""


def _maintainer_checklist() -> str:
    return """# Maintainer Launch Checklist

Do not publish until every item is checked.

- [ ] `publication-gate` remains hold during private review.
- [ ] Live Mac microphone capture has been validated.
- [ ] `real-capture-execution-gate` passes with live artifacts.
- [ ] `local-asr-smoke-gate` passes with faster-whisper evidence or documented fallback.
- [ ] README includes clear limitations and no overclaims.
- [ ] Screenshots/GIFs are curated and do not expose private data.
- [ ] No private prompts, private datasets, credentials, or commercial-only internals are included.
- [ ] Maintainer explicitly flips `public_oss_announcement_allowed` only when ready.
"""


def _private_core_boundary() -> str:
    return """# Private Core Boundary Summary

## Community shell

- Transcript schema
- Basic evidence-linked minutes
- Audio diagnostics
- Validation packs
- Desktop Alpha UI and Bridge
- ASR provider interfaces and sidecar/faster-whisper scaffolding

## Protected core candidates

- High-accuracy Japanese correction engine
- Advanced verifier pipeline
- Model router and cost/quality optimizer
- Private evaluation dataset
- Speaker-name mapping
- Enterprise admin, billing, SSO, and audit console
"""


def _screenshot_guide() -> str:
    return """# Screenshot Guide

Capture these screens for launch review:

1. Desktop Alpha connected state.
2. Evidence-linked minutes HTML.
3. Audio readiness panel.
4. Local ASR smoke gate.
5. Public Alpha Readiness showing hold/blockers.

Recommended file names:

- `01_desktop_alpha_connected.png`
- `02_minutes_evidence.png`
- `03_audio_readiness.png`
- `04_local_asr_smoke.png`
- `05_public_alpha_hold.png`
"""


def _release_notes_draft() -> str:
    return f"""# Release Notes Draft — v{__version__}

> Private draft. Do not publish yet.

## Highlights

- Desktop Alpha UI and local bridge
- Evidence-linked minutes
- Audio diagnostics and capture safety gates
- Post-capture, ASR validation, ASR→minutes, and local ASR smoke workflows
- Launch asset/readiness gates

## Status

Public alpha is still on hold pending real microphone and local ASR evidence.
"""


def _faq_draft() -> str:
    return """# FAQ Draft

## Is this production-ready?

No. This is a private developer preview.

## Does it include the private quality engine?

No. `private_core_included` must remain `false`.

## Can it record real meetings today?

Real microphone capture is being validated. Always notify participants and obtain consent before recording.

## Is OSS publication allowed now?

No. Publication remains blocked until maintainer approval.
"""


def _verify_private_hold_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=src python -m meeting_agent publication-gate --root .
PYTHONPATH=src python -m meeting_agent public-alpha-readiness --root .
PYTHONPATH=src python -m meeting_agent launch-polish-check --root . --launch-assets-dir launch_assets
"""
