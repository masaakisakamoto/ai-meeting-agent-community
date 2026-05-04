from __future__ import annotations

import json
import platform
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent import __version__
from meeting_agent.core.schemas import utc_now_iso
from meeting_agent.release.publication import run_publication_gate


@dataclass(frozen=True)
class ExportCheck:
    id: str
    status: str
    detail: str
    category: str = "evidence_export"
    required_for_public_alpha: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceExportReport:
    status: str
    score: float
    generated_at: str
    recommendation: str
    checks: list[ExportCheck]
    artifacts: dict[str, str]
    summary: dict[str, Any]
    publication_hold: bool = True
    opens_microphone: bool = False
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Evidence Export Report",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Publication hold: `{str(self.publication_hold).lower()}`",
            f"- Opens microphone: `{str(self.opens_microphone).lower()}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            f"- Generated at: `{self.generated_at}`",
            "",
            "## Recommendation",
            "",
            self.recommendation,
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
            lines.append(f"| {check.id} | `{check.status}` | `{str(check.required_for_public_alpha).lower()}` | {check.category} | {_md(check.detail)} |")
        lines.extend(["", "## Artifacts", "", "| Name | Path |", "|---|---|"])
        for name, path in sorted(self.artifacts.items()):
            lines.append(f"| {name} | `{path}` |")
        lines.append("")
        return "\n".join(lines)


@dataclass(frozen=True)
class EvidenceExportPackReport:
    status: str
    score: float
    generated_at: str
    out_dir: str
    recommendation: str
    commands: dict[str, str]
    checks: list[ExportCheck]
    artifacts: dict[str, str]
    publication_hold: bool = True
    opens_microphone: bool = False
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Evidence Export & Screenshot Automation Pack",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Output directory: `{self.out_dir}`",
            f"- Publication hold: `{str(self.publication_hold).lower()}`",
            f"- Opens microphone: `{str(self.opens_microphone).lower()}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            f"- Generated at: `{self.generated_at}`",
            "",
            "## Purpose",
            "",
            "This private pack prepares README-ready evidence exports, screenshot shot lists, and deterministic verification scripts. It does not open the microphone and does not publish anything.",
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
class ScreenshotAutomationReport:
    status: str
    score: float
    generated_at: str
    recommendation: str
    shotlist: list[dict[str, Any]]
    checks: list[ExportCheck]
    artifacts: dict[str, str]
    summary: dict[str, Any]
    publication_hold: bool = True
    opens_microphone: bool = False
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Screenshot Automation Prep",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Publication hold: `{str(self.publication_hold).lower()}`",
            f"- Opens microphone: `{str(self.opens_microphone).lower()}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            f"- Generated at: `{self.generated_at}`",
            "",
            "## Recommendation",
            "",
            self.recommendation,
            "",
            "## Shotlist",
            "",
            "| ID | Title | URL / Path | Required | Notes |",
            "|---|---|---|---:|---|",
        ]
        for shot in self.shotlist:
            lines.append(f"| {shot.get('id')} | {_md(str(shot.get('title', '')))} | `{_md(str(shot.get('target', '')))} ` | `{str(shot.get('required', False)).lower()}` | {_md(str(shot.get('notes', '')))} |")
        lines.extend(["", "## Checks", "", "| Check | Status | Required | Detail |", "|---|---|---:|---|"])
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | `{str(check.required_for_public_alpha).lower()}` | {_md(check.detail)} |")
        lines.extend(["", "## Artifacts", "", "| Name | Path |", "|---|---|"])
        for name, path in sorted(self.artifacts.items()):
            lines.append(f"| {name} | `{path}` |")
        lines.append("")
        return "\n".join(lines)


def build_evidence_export_pack(
    *,
    out_dir: str | Path,
    root: str | Path = ".",
    export_dir: str | Path = "evidence_export",
    demo_dir: str | Path = "demo_out",
    evidence_dir: str | Path = "real_mac_evidence",
    launch_assets_dir: str | Path = "launch_assets",
    dashboard_dir: str | Path = "maintainer_dashboard",
    screenshot_dir: str | Path = "screenshots",
    bridge_url: str = "http://127.0.0.1:8765",
) -> EvidenceExportPackReport:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scripts").mkdir(exist_ok=True)

    commands = {
        "01_build_screenshot_pack": (
            "PYTHONPATH=src python -m meeting_agent screenshot-automation-pack "
            f"--out-dir {out}/screenshot_automation --demo-dir {demo_dir} --bridge-url {bridge_url} --screenshot-dir {screenshot_dir}"
        ),
        "02_export_evidence": (
            "PYTHONPATH=src python -m meeting_agent evidence-export-run "
            f"--root {root} --out-dir {export_dir} --demo-dir {demo_dir} --evidence-dir {evidence_dir} "
            f"--launch-assets-dir {launch_assets_dir} --dashboard-dir {dashboard_dir} --screenshot-dir {screenshot_dir}"
        ),
        "03_verify_export": (
            "PYTHONPATH=src python -m meeting_agent evidence-export-gate "
            f"--root {root} --export-dir {export_dir} --screenshot-dir {screenshot_dir} --out-json evidence_export_gate.json --out-md evidence_export_gate.md"
        ),
        "04_keep_publication_locked": "PYTHONPATH=src python -m meeting_agent publication-gate --root .",
    }
    artifacts: dict[str, str] = {}
    for name, command in commands.items():
        script = out / "scripts" / f"{name}.sh"
        _write(script, "#!/usr/bin/env bash\nset -euo pipefail\n\n" + command + "\n")
        _chmod(script)
        artifacts[f"scripts/{script.name}"] = str(script)

    _write(out / "README.md", _evidence_export_readme(export_dir, screenshot_dir, bridge_url))
    _write(out / "EXPORT_COMMANDS.md", _commands_markdown(commands))
    _write(out / "README_SNIPPETS.md", _readme_snippets())
    _write(out / "SCREENSHOT_AUTOMATION_PLAN.md", _screenshot_plan_markdown(bridge_url, demo_dir, screenshot_dir))
    _write(out / "EVIDENCE_INDEX_TEMPLATE.md", _evidence_index_template())
    manifest = {
        "schema_version": "evidence-export-pack/v1",
        "project": "ai-meeting-agent-community",
        "version": __version__,
        "stage": "private_developer_preview",
        "publication_policy": "hold",
        "opens_microphone": False,
        "private_core_included": False,
        "created_at": utc_now_iso(),
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
        "inputs": {
            "root": str(root),
            "export_dir": str(export_dir),
            "demo_dir": str(demo_dir),
            "evidence_dir": str(evidence_dir),
            "launch_assets_dir": str(launch_assets_dir),
            "dashboard_dir": str(dashboard_dir),
            "screenshot_dir": str(screenshot_dir),
            "bridge_url": bridge_url,
        },
        "commands": commands,
    }
    _write_json(out / "evidence_export_manifest.json", manifest)

    for rel in ["README.md", "EXPORT_COMMANDS.md", "README_SNIPPETS.md", "SCREENSHOT_AUTOMATION_PLAN.md", "EVIDENCE_INDEX_TEMPLATE.md", "evidence_export_manifest.json"]:
        artifacts[rel] = str(out / rel)
    checks = [
        ExportCheck("publication_hold", "pass", "Pack preserves publication hold and does not publish.", "guardrail", True),
        ExportCheck("opens_microphone", "pass", "Pack generation does not open microphone.", "safety", True),
        ExportCheck("private_core_excluded", "pass", "No private-core code is included in this pack.", "commercial_guardrail", True),
        ExportCheck("screenshot_plan", "pass", "Screenshot automation plan generated.", "launch_assets", False),
        ExportCheck("readme_snippets", "pass", "README-ready snippets generated for later manual review.", "launch_assets", False),
    ]
    report = EvidenceExportPackReport(
        status="pass",
        score=1.0,
        generated_at=utc_now_iso(),
        out_dir=str(out),
        recommendation="Evidence export pack is ready for private review. Keep publication-gate on hold until real Mac evidence, screenshots, and maintainer approval are complete.",
        commands=commands,
        checks=checks,
        artifacts=artifacts,
        publication_hold=True,
        opens_microphone=False,
        private_core_included=False,
    )
    _write(out / "evidence_export_pack.json", report.to_json() + "\n")
    _write(out / "evidence_export_pack.md", report.to_markdown())
    return report


def build_screenshot_automation_pack(
    *,
    out_dir: str | Path,
    root: str | Path = ".",
    demo_dir: str | Path = "demo_out",
    bridge_url: str = "http://127.0.0.1:8765",
    screenshot_dir: str | Path = "screenshots",
) -> ScreenshotAutomationReport:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scripts").mkdir(exist_ok=True)
    shotlist = default_shotlist(bridge_url=bridge_url, demo_dir=str(demo_dir))
    artifacts: dict[str, str] = {}
    _write_json(out / "shotlist.json", {"shots": shotlist, "private_core_included": False, "publication_hold": True})
    _write(out / "shotlist.md", _shotlist_markdown(shotlist))
    _write(out / "README.md", _screenshot_automation_readme(bridge_url, screenshot_dir))
    open_script = out / "scripts" / "01_open_review_targets.sh"
    capture_script = out / "scripts" / "02_prepare_screenshot_folder.sh"
    _write(open_script, _open_targets_script(shotlist))
    _write(capture_script, _prepare_screenshot_folder_script(screenshot_dir))
    _chmod(open_script)
    _chmod(capture_script)
    artifacts.update({
        "README.md": str(out / "README.md"),
        "shotlist.json": str(out / "shotlist.json"),
        "shotlist.md": str(out / "shotlist.md"),
        "scripts/01_open_review_targets.sh": str(open_script),
        "scripts/02_prepare_screenshot_folder.sh": str(capture_script),
    })
    checks = [
        ExportCheck("shotlist_minimum", "pass" if len(shotlist) >= 5 else "warn", f"{len(shotlist)} planned screenshots.", "screenshots", True),
        ExportCheck("publication_hold", "pass", "Screenshot pack does not publish anything.", "guardrail", True),
        ExportCheck("opens_microphone", "pass", "Screenshot pack does not open microphone.", "safety", True),
        ExportCheck("private_core_excluded", "pass", "No private-core code included.", "commercial_guardrail", True),
    ]
    report = ScreenshotAutomationReport(
        status="pass" if all(c.status == "pass" for c in checks if c.required_for_public_alpha) else "warn",
        score=_score(checks),
        generated_at=utc_now_iso(),
        recommendation="Screenshot automation prep is ready. Capture at least 3 curated screenshots after real Mac evidence is available.",
        shotlist=shotlist,
        checks=checks,
        artifacts=artifacts,
        summary={"planned_shots": len(shotlist), "screenshot_dir": str(screenshot_dir), "bridge_url": bridge_url},
        publication_hold=True,
        opens_microphone=False,
        private_core_included=False,
    )
    _write(out / "screenshot_automation_pack.json", report.to_json() + "\n")
    _write(out / "screenshot_automation_pack.md", report.to_markdown())
    return report


def export_evidence_bundle(
    *,
    root: str | Path = ".",
    out_dir: str | Path = "evidence_export",
    demo_dir: str | Path = "demo_out",
    evidence_dir: str | Path = "real_mac_evidence",
    launch_assets_dir: str | Path = "launch_assets",
    dashboard_dir: str | Path = "maintainer_dashboard",
    screenshot_dir: str | Path = "screenshots",
    copy_artifacts: bool = True,
) -> EvidenceExportReport:
    root_path = Path(root)
    out = Path(out_dir)
    if not out.is_absolute():
        out = root_path / out
    out.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}
    checks: list[ExportCheck] = []

    publication = run_publication_gate(root_path)
    hold = publication.status == "hold"
    checks.append(ExportCheck("publication_hold", "pass" if hold else "fail", f"Publication gate status: {publication.status}", "guardrail", True))

    sources = {
        "demo_minutes_html": _resolve(root_path, demo_dir, "minutes.html"),
        "desktop_alpha_ui": _resolve(root_path, demo_dir, "desktop_alpha/app/index.html"),
        "maintainer_dashboard_html": _resolve(root_path, demo_dir, "maintainer_dashboard.html"),
        "public_alpha_readiness_md": _resolve(root_path, demo_dir, "public_alpha_readiness.md"),
        "candidate_gate_md": _resolve(root_path, demo_dir, "public_alpha_candidate_gate.md"),
        "publication_gate_md": _resolve(root_path, demo_dir, "publication_gate.md"),
        "launch_readme_draft": _resolve(root_path, launch_assets_dir, "README_PUBLIC_ALPHA_DRAFT.md"),
        "launch_known_limitations": _resolve(root_path, launch_assets_dir, "KNOWN_LIMITATIONS.md"),
        "real_mac_evidence_md": _resolve(root_path, evidence_dir, "real_mac_evidence.md"),
    }
    if not sources["maintainer_dashboard_html"].exists():
        alt = _resolve(root_path, dashboard_dir, "maintainer_dashboard.html")
        if alt.exists():
            sources["maintainer_dashboard_html"] = alt

    required = {"demo_minutes_html", "desktop_alpha_ui", "publication_gate_md"}
    for name, path in sources.items():
        is_required = name in required
        status = "pass" if path.exists() else ("warn" if is_required else "warn")
        detail = f"{name} present: {path}" if path.exists() else f"{name} missing: {path}"
        checks.append(ExportCheck(name, status, detail, "evidence_source", is_required, {"path": str(path)}))
        if path.exists() and copy_artifacts:
            target = out / "artifacts" / name / path.name
            _copy(path, target)
            artifacts[f"artifacts/{name}/{path.name}"] = str(target)

    screenshots = _list_screenshots(_resolve(root_path, screenshot_dir)) + _list_screenshots(_resolve(root_path, demo_dir, "screenshots"))
    screenshots = _dedupe_paths(screenshots)
    if copy_artifacts:
        for shot in screenshots:
            target = out / "screenshots" / shot.name
            _copy(shot, target)
            artifacts[f"screenshots/{shot.name}"] = str(target)
    screenshot_status = "pass" if len(screenshots) >= 3 else "warn"
    checks.append(ExportCheck("screenshots_minimum", screenshot_status, f"{len(screenshots)} screenshot(s) found; 3 required before public announcement.", "screenshots", True, {"count": len(screenshots)}))

    private_hits = _scan_private_core_dirs(root_path)
    checks.append(ExportCheck("private_core_excluded", "pass" if not private_hits else "fail", "No private-core directories detected." if not private_hits else f"Private-looking directories detected: {private_hits}", "commercial_guardrail", True, {"hits": private_hits}))

    index = {
        "schema_version": "evidence-export/v1",
        "project": "ai-meeting-agent-community",
        "version": __version__,
        "generated_at": utc_now_iso(),
        "publication_hold": hold,
        "private_core_included": bool(private_hits),
        "copy_artifacts": copy_artifacts,
        "source_paths": {name: str(path) for name, path in sources.items()},
        "screenshots": [str(path) for path in screenshots],
        "artifacts": artifacts,
        "checks": [check.to_dict() for check in checks],
    }
    _write_json(out / "evidence_index.json", index)
    _write(out / "evidence_index.md", _evidence_index_markdown(index))
    _write(out / "README.md", _export_bundle_readme())
    _write(out / "README_SNIPPETS.md", _readme_snippets())
    artifacts["evidence_index.json"] = str(out / "evidence_index.json")
    artifacts["evidence_index.md"] = str(out / "evidence_index.md")
    artifacts["README.md"] = str(out / "README.md")
    artifacts["README_SNIPPETS.md"] = str(out / "README_SNIPPETS.md")

    status = "pass"
    if any(c.status == "fail" for c in checks):
        status = "fail"
    elif any(c.status == "warn" for c in checks if c.required_for_public_alpha):
        status = "warn"
    report = EvidenceExportReport(
        status=status,
        score=_score(checks),
        generated_at=utc_now_iso(),
        recommendation=_export_recommendation(status, len(screenshots), hold),
        checks=checks,
        artifacts=artifacts,
        summary={"export_dir": str(out), "screenshots": len(screenshots), "sources": len(sources), "publication_hold": hold},
        publication_hold=hold,
        opens_microphone=False,
        private_core_included=bool(private_hits),
    )
    _write(out / "evidence_export_report.json", report.to_json() + "\n")
    _write(out / "evidence_export_report.md", report.to_markdown())
    return report


def run_evidence_export_gate(
    *,
    root: str | Path = ".",
    export_dir: str | Path = "evidence_export",
    screenshot_dir: str | Path = "screenshots",
    min_screenshots: int = 3,
) -> EvidenceExportReport:
    root_path = Path(root)
    out = Path(export_dir)
    if not out.is_absolute():
        out = root_path / out
    checks: list[ExportCheck] = []
    report_json = out / "evidence_export_report.json"
    index_json = out / "evidence_index.json"
    checks.append(ExportCheck("evidence_export_report", "pass" if report_json.exists() else "warn", f"Evidence export report {'present' if report_json.exists() else 'missing'}.", "evidence_export", True, {"path": str(report_json)}))
    checks.append(ExportCheck("evidence_index", "pass" if index_json.exists() else "warn", f"Evidence index {'present' if index_json.exists() else 'missing'}.", "evidence_export", True, {"path": str(index_json)}))
    screenshots = _list_screenshots(out / "screenshots") + _list_screenshots(_resolve(root_path, screenshot_dir))
    screenshots = _dedupe_paths(screenshots)
    checks.append(ExportCheck("screenshots_minimum", "pass" if len(screenshots) >= min_screenshots else "warn", f"{len(screenshots)} screenshot(s) found; {min_screenshots} required.", "screenshots", True, {"count": len(screenshots), "minimum": min_screenshots}))
    publication = run_publication_gate(root_path)
    checks.append(ExportCheck("publication_hold", "pass" if publication.status == "hold" else "fail", f"Publication gate status: {publication.status}", "guardrail", True))
    private_hits = _scan_private_core_dirs(root_path)
    checks.append(ExportCheck("private_core_excluded", "pass" if not private_hits else "fail", "No private-core directories detected." if not private_hits else f"Private-looking directories detected: {private_hits}", "commercial_guardrail", True, {"hits": private_hits}))
    status = "pass"
    if any(c.status == "fail" for c in checks):
        status = "fail"
    elif any(c.status == "warn" for c in checks if c.required_for_public_alpha):
        status = "warn"
    return EvidenceExportReport(
        status=status,
        score=_score(checks),
        generated_at=utc_now_iso(),
        recommendation=_export_recommendation(status, len(screenshots), publication.status == "hold"),
        checks=checks,
        artifacts={"export_dir": str(out), "report": str(report_json), "index": str(index_json)},
        summary={"export_dir": str(out), "screenshots": len(screenshots), "min_screenshots": min_screenshots, "publication_hold": publication.status == "hold"},
        publication_hold=publication.status == "hold",
        opens_microphone=False,
        private_core_included=bool(private_hits),
    )


def run_screenshot_readiness_gate(
    *,
    root: str | Path = ".",
    screenshot_dir: str | Path = "screenshots",
    demo_dir: str | Path = "demo_out",
    min_screenshots: int = 3,
) -> ScreenshotAutomationReport:
    root_path = Path(root)
    screenshots = _dedupe_paths(_list_screenshots(_resolve(root_path, screenshot_dir)) + _list_screenshots(_resolve(root_path, demo_dir, "screenshots")))
    checks = [
        ExportCheck("screenshots_minimum", "pass" if len(screenshots) >= min_screenshots else "warn", f"{len(screenshots)} screenshot(s) found; {min_screenshots} required.", "screenshots", True, {"count": len(screenshots)}),
        ExportCheck("desktop_ui_demo", "pass" if _resolve(root_path, demo_dir, "desktop_alpha/app/index.html").exists() else "warn", "Desktop Alpha UI demo present." if _resolve(root_path, demo_dir, "desktop_alpha/app/index.html").exists() else "Desktop Alpha UI demo missing.", "screenshots", False),
        ExportCheck("maintainer_dashboard_demo", "pass" if _resolve(root_path, demo_dir, "maintainer_dashboard.html").exists() else "warn", "Maintainer dashboard demo present." if _resolve(root_path, demo_dir, "maintainer_dashboard.html").exists() else "Maintainer dashboard demo missing.", "screenshots", False),
        ExportCheck("private_core_excluded", "pass", "No private-core code required for screenshot readiness.", "commercial_guardrail", True),
    ]
    status = "pass" if all(c.status == "pass" for c in checks if c.required_for_public_alpha) else "warn"
    return ScreenshotAutomationReport(
        status=status,
        score=_score(checks),
        generated_at=utc_now_iso(),
        recommendation="Screenshot readiness is sufficient for public alpha review." if status == "pass" else "Capture at least 3 curated screenshots before public alpha announcement.",
        shotlist=default_shotlist(bridge_url="http://127.0.0.1:8765", demo_dir=str(demo_dir)),
        checks=checks,
        artifacts={"screenshot_dir": str(_resolve(root_path, screenshot_dir)), "demo_screenshot_dir": str(_resolve(root_path, demo_dir, "screenshots"))},
        summary={"screenshots": len(screenshots), "min_screenshots": min_screenshots},
        publication_hold=True,
        opens_microphone=False,
        private_core_included=False,
    )


def write_evidence_export_pack_report(report: EvidenceExportPackReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    _write_report(report, out_json=out_json, out_md=out_md)


def write_evidence_export_report(report: EvidenceExportReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    _write_report(report, out_json=out_json, out_md=out_md)


def write_screenshot_automation_report(report: ScreenshotAutomationReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    _write_report(report, out_json=out_json, out_md=out_md)


def default_shotlist(*, bridge_url: str, demo_dir: str) -> list[dict[str, Any]]:
    return [
        {"id": "desktop-alpha-connected", "title": "Desktop Alpha Bridge Connected", "target": bridge_url, "required": True, "notes": "Show Bridge Connected, workflow buttons, and publication hold context."},
        {"id": "evidence-linked-minutes", "title": "Evidence-linked Minutes HTML", "target": f"{demo_dir}/minutes.html", "required": True, "notes": "Show decisions/action items with source evidence."},
        {"id": "maintainer-dashboard", "title": "Maintainer Evidence Dashboard", "target": f"{demo_dir}/maintainer_dashboard.html", "required": True, "notes": "Show hold decision and private-core exclusion."},
        {"id": "public-alpha-readiness", "title": "Public Alpha Readiness Gate", "target": f"{demo_dir}/public_alpha_readiness.md", "required": False, "notes": "Show remaining blockers."},
        {"id": "candidate-gate", "title": "Public Alpha Candidate Gate", "target": f"{demo_dir}/public_alpha_candidate_gate.md", "required": False, "notes": "Show candidate gate status."},
        {"id": "audio-readiness", "title": "Audio Readiness / Level Meter", "target": bridge_url, "required": False, "notes": "Show audio diagnostics and readiness cards in the UI."},
    ]


# Helpers

def _resolve(root: Path, base: str | Path, rel: str | Path | None = None) -> Path:
    path = Path(base)
    if not path.is_absolute():
        path = root / path
    if rel is not None:
        path = path / rel
    return path


def _write(path: str | Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: str | Path, payload: Any) -> None:
    _write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _write_report(report: Any, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        _write(out_json, report.to_json() + "\n")
    if out_md:
        _write(out_md, report.to_markdown())


def _copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _chmod(path: Path) -> None:
    try:
        path.chmod(0o755)
    except OSError:
        pass


def _list_screenshots(path: Path) -> list[Path]:
    if not path.exists() or not path.is_dir():
        return []
    exts = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    return [item for item in sorted(path.rglob("*")) if item.is_file() and item.suffix.lower() in exts]


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            result.append(path)
            seen.add(key)
    return result


def _scan_private_core_dirs(root: Path) -> list[str]:
    suspicious = []
    names = {"private_core", "quality_engine_private", "commercial_core", "enterprise_private", "private-evals", "private_evals"}
    for path in root.rglob("*"):
        if path.is_dir() and path.name in names:
            suspicious.append(str(path.relative_to(root)))
    return suspicious[:20]


def _score(checks: list[ExportCheck]) -> float:
    if not checks:
        return 1.0
    weights = {"pass": 1.0, "warn": 0.55, "fail": 0.0, "hold": 0.65}
    return round(sum(weights.get(c.status, 0.0) for c in checks) / len(checks), 3)


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _evidence_export_readme(export_dir: str | Path, screenshot_dir: str | Path, bridge_url: str) -> str:
    return f"""# Evidence Export Pack

This private pack prepares a README-ready evidence bundle for AI Meeting Agent Community.

- Publication remains on hold.
- This pack does not open the microphone.
- This pack does not include private-core code.

## Recommended private flow

```bash
PYTHONPATH=src python -m meeting_agent screenshot-automation-pack --out-dir screenshot_automation --bridge-url {bridge_url}
PYTHONPATH=src python -m meeting_agent evidence-export-run --out-dir {export_dir} --screenshot-dir {screenshot_dir}
PYTHONPATH=src python -m meeting_agent evidence-export-gate --export-dir {export_dir} --screenshot-dir {screenshot_dir}
```
"""


def _commands_markdown(commands: dict[str, str]) -> str:
    lines = ["# Evidence Export Commands", ""]
    for name, command in commands.items():
        lines.extend([f"## {name}", "", "```bash", command, "```", ""])
    return "\n".join(lines)


def _readme_snippets() -> str:
    return """# README Snippets

## Suggested private-preview description

AI Meeting Agent Community is a local-first, evidence-linked meeting intelligence prototype. Public Alpha publication is intentionally on hold until real Mac microphone evidence, local ASR smoke evidence, screenshots, and maintainer approval are complete.

## Suggested evidence bullets

- Evidence-linked minutes with source transcript references.
- Desktop Alpha UI with local Bridge APIs.
- Publication Gate remains on hold until explicit maintainer unlock.
- Private Quality Engine is not included in the Community package.

## Suggested limitation language

This repository is not a production recorder yet. Real microphone capture, local ASR, and packaging should be validated on target machines before any public announcement.
"""


def _screenshot_plan_markdown(bridge_url: str, demo_dir: str | Path, screenshot_dir: str | Path) -> str:
    return "# Screenshot Automation Plan\n\n" + _shotlist_markdown(default_shotlist(bridge_url=bridge_url, demo_dir=str(demo_dir))) + f"\n\nStore curated screenshots under `{screenshot_dir}`.\n"


def _evidence_index_template() -> str:
    return """# Evidence Index Template

| Area | Artifact | Status | Notes |
|---|---|---|---|
| Desktop Alpha | screenshot | pending | Capture through Bridge URL. |
| Evidence-linked minutes | minutes.html | pending | Show source evidence. |
| Maintainer dashboard | maintainer_dashboard.html | pending | Show hold decision. |
| Real Mac capture | audio.wav + audit.jsonl | pending | Required before public alpha. |
| Local ASR smoke | asr_minutes_report.json | pending | Required before public alpha. |
"""


def _screenshot_automation_readme(bridge_url: str, screenshot_dir: str | Path) -> str:
    return f"""# Screenshot Automation Prep

This pack prepares the shot list and helper scripts for public-alpha screenshots.

- Bridge URL: `{bridge_url}`
- Screenshot output directory: `{screenshot_dir}`
- Publication remains on hold.
- The scripts do not open the microphone.

Run `scripts/01_open_review_targets.sh`, then capture screenshots manually or with macOS `screencapture`.
"""


def _shotlist_markdown(shotlist: list[dict[str, Any]]) -> str:
    lines = ["# Screenshot Shotlist", "", "| ID | Title | Target | Required | Notes |", "|---|---|---|---:|---|"]
    for shot in shotlist:
        lines.append(f"| {shot['id']} | {_md(shot['title'])} | `{_md(shot['target'])}` | `{str(shot.get('required', False)).lower()}` | {_md(shot.get('notes', ''))} |")
    return "\n".join(lines) + "\n"


def _open_targets_script(shotlist: list[dict[str, Any]]) -> str:
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", "", "echo 'Opening screenshot review targets...'" ]
    for shot in shotlist:
        target = str(shot.get("target", ""))
        if target.startswith("http://") or target.startswith("https://"):
            lines.append(f"open '{target}' || true")
    lines.append("echo 'Open local file targets manually if needed from the shotlist.'")
    return "\n".join(lines) + "\n"


def _prepare_screenshot_folder_script(screenshot_dir: str | Path) -> str:
    return f"#!/usr/bin/env bash\nset -euo pipefail\nmkdir -p '{screenshot_dir}'\necho 'Capture screenshots into {screenshot_dir}'\n"


def _evidence_index_markdown(index: dict[str, Any]) -> str:
    lines = ["# Evidence Export Index", "", f"- Version: `{index.get('version')}`", f"- Publication hold: `{str(index.get('publication_hold')).lower()}`", f"- Private core included: `{str(index.get('private_core_included')).lower()}`", "", "## Source paths", "", "| Name | Path |", "|---|---|"]
    for name, path in sorted(index.get("source_paths", {}).items()):
        lines.append(f"| {name} | `{path}` |")
    lines.extend(["", "## Screenshots", ""])
    shots = index.get("screenshots", [])
    if shots:
        lines.extend(f"- `{shot}`" for shot in shots)
    else:
        lines.append("- No screenshots collected yet.")
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "|---|---|---|"])
    for check in index.get("checks", []):
        lines.append(f"| {check.get('id')} | `{check.get('status')}` | {_md(str(check.get('detail', '')))} |")
    lines.append("")
    return "\n".join(lines)


def _export_bundle_readme() -> str:
    return """# Evidence Export Bundle

This private bundle consolidates public-alpha review evidence. It is safe to keep private and review manually.

Do not publish this bundle until publication-gate is intentionally unlocked by the maintainer.
"""


def _export_recommendation(status: str, screenshots: int, publication_hold: bool) -> str:
    if status == "fail":
        return "Evidence export failed. Fix private-core or publication policy issues before continuing."
    if screenshots < 3:
        return "Evidence export is usable for private review, but capture at least 3 curated screenshots before public alpha."
    if publication_hold:
        return "Evidence export is ready for private maintainer review. Publication is still intentionally on hold."
    return "Evidence export is ready, but verify maintainer approval and rollback plan before publishing."
