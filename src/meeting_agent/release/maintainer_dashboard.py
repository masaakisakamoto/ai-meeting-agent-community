from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent import __version__
from meeting_agent.core.schemas import utc_now_iso
from meeting_agent.release.evidence_collection import collect_real_mac_evidence
from meeting_agent.release.launch_assets import run_launch_polish_check
from meeting_agent.release.public_alpha import run_public_alpha_readiness
from meeting_agent.release.public_alpha_candidate import run_public_alpha_candidate_gate
from meeting_agent.release.publication import run_publication_gate
from meeting_agent.release.readiness import run_release_readiness


@dataclass(frozen=True)
class MaintainerDashboardCheck:
    id: str
    status: str
    detail: str
    category: str = "dashboard"
    required_for_public_alpha: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MaintainerReviewPackReport:
    status: str
    score: float
    out_dir: str
    generated_at: str
    recommendation: str
    commands: dict[str, str]
    artifacts: dict[str, str]
    checks: list[MaintainerDashboardCheck]
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
            "# Maintainer Review Pack",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Output directory: `{self.out_dir}`",
            f"- Publication hold: `{str(self.publication_hold).lower()}`",
            f"- Opens microphone: `{str(self.opens_microphone).lower()}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            f"- Generated at: `{self.generated_at}`",
            "",
            "## Recommendation",
            "",
            self.recommendation,
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
        lines.append("")
        return "\n".join(lines)


@dataclass(frozen=True)
class MaintainerDashboardReport:
    status: str
    score: float
    generated_at: str
    recommendation: str
    estimated_public_unlock: str
    decision: str
    checks: list[MaintainerDashboardCheck]
    blockers: list[str]
    next_actions: list[str]
    artifacts: dict[str, str]
    summary: dict[str, Any]
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
            "# Maintainer Evidence Dashboard",
            "",
            f"- Status: `{self.status}`",
            f"- Decision: `{self.decision}`",
            f"- Score: `{self.score}`",
            f"- Estimated public unlock: `{self.estimated_public_unlock}`",
            f"- Publication hold: `{str(self.publication_hold).lower()}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            f"- Generated at: `{self.generated_at}`",
            "",
            "## Recommendation",
            "",
            self.recommendation,
            "",
            "## Summary",
            "",
            "| Signal | Value |",
            "|---|---|",
        ]
        for key, value in sorted(self.summary.items()):
            lines.append(f"| {key} | `{_md(str(value))}` |")
        lines.extend(["", "## Checks", "", "| Check | Status | Required | Category | Detail |", "|---|---|---:|---|---|"])
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | `{str(check.required_for_public_alpha).lower()}` | {check.category} | {_md(check.detail)} |")
        if self.blockers:
            lines.extend(["", "## Blockers", ""])
            lines.extend(f"- {item}" for item in self.blockers)
        lines.extend(["", "## Next actions", ""])
        lines.extend(f"- {item}" for item in self.next_actions)
        lines.extend(["", "## Artifacts", "", "| Name | Path |", "|---|---|"])
        for name, path in sorted(self.artifacts.items()):
            lines.append(f"| {name} | `{path}` |")
        lines.append("")
        return "\n".join(lines)

    def to_html(self) -> str:
        status_class = _safe_class(self.status)
        check_cards = "\n".join(
            f"""
            <article class=\"check { _safe_class(check.status) }\">
              <div class=\"check-head\"><strong>{_html(check.id)}</strong><span>{_html(check.status)}</span></div>
              <p>{_html(check.detail)}</p>
              <small>{_html(check.category)} · required={str(check.required_for_public_alpha).lower()}</small>
            </article>
            """
            for check in self.checks
        )
        blockers = "".join(f"<li>{_html(item)}</li>" for item in self.blockers) or "<li>No release blockers detected by this dashboard.</li>"
        next_actions = "".join(f"<li>{_html(item)}</li>" for item in self.next_actions)
        summary = "".join(f"<tr><th>{_html(k)}</th><td>{_html(v)}</td></tr>" for k, v in sorted(self.summary.items()))
        artifacts = "".join(f"<tr><th>{_html(name)}</th><td><code>{_html(path)}</code></td></tr>" for name, path in sorted(self.artifacts.items()))
        return f"""<!doctype html>
<html lang=\"ja\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Maintainer Evidence Dashboard</title>
  <style>
    :root {{ color-scheme: light dark; --ok:#1f8f4d; --warn:#b7791f; --hold:#6b46c1; --fail:#c53030; --ink:#172033; --muted:#667085; --bg:#f7f7fb; --card:#ffffff; }}
    body {{ margin:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:var(--bg); color:var(--ink); }}
    header {{ padding:32px; background:linear-gradient(135deg,#1d2340,#3e4c89); color:white; }}
    header p {{ max-width:920px; color:#e7e9ff; }}
    main {{ padding:24px; max-width:1180px; margin:0 auto; }}
    .hero {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); gap:16px; margin-top:-44px; }}
    .metric, .panel, .check {{ background:var(--card); border-radius:18px; padding:18px; box-shadow:0 16px 40px rgba(31,41,55,.08); border:1px solid rgba(99,102,241,.12); }}
    .metric strong {{ display:block; font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }}
    .metric span {{ display:block; font-size:26px; margin-top:8px; font-weight:750; }}
    .status-{status_class} span {{ color: var(--hold); }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(280px,1fr)); gap:14px; }}
    .check-head {{ display:flex; justify-content:space-between; gap:12px; }}
    .check-head span {{ border-radius:999px; padding:4px 10px; background:#eef2ff; color:#334155; font-size:12px; }}
    .check.pass .check-head span {{ background:#dcfce7; color:var(--ok); }}
    .check.warn .check-head span {{ background:#fef3c7; color:var(--warn); }}
    .check.hold .check-head span, .check.hold_missing_candidate_evidence .check-head span {{ background:#ede9fe; color:var(--hold); }}
    .check.fail .check-head span {{ background:#fee2e2; color:var(--fail); }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ text-align:left; border-bottom:1px solid #e5e7eb; padding:10px; vertical-align:top; }}
    code {{ white-space:pre-wrap; }}
    @media (prefers-color-scheme: dark) {{ :root {{ --bg:#0b1020; --card:#111827; --ink:#f8fafc; --muted:#a1a1aa; }} th,td {{ border-bottom-color:#293145; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Maintainer Evidence Dashboard</h1>
    <p>Public Alpha候補の公開可否を、実Mac証跡・ASR・Launch素材・Candidate Gate・公開保留ポリシーから一括確認するためのPrivate Maintainer画面です。</p>
  </header>
  <main>
    <section class=\"hero\">
      <div class=\"metric status-{status_class}\"><strong>Status</strong><span>{_html(self.status)}</span></div>
      <div class=\"metric\"><strong>Decision</strong><span>{_html(self.decision)}</span></div>
      <div class=\"metric\"><strong>Score</strong><span>{self.score}</span></div>
      <div class=\"metric\"><strong>Publication hold</strong><span>{str(self.publication_hold).lower()}</span></div>
    </section>
    <section class=\"panel\"><h2>Recommendation</h2><p>{_html(self.recommendation)}</p></section>
    <section class=\"panel\"><h2>Summary</h2><table>{summary}</table></section>
    <section class=\"panel\"><h2>Checks</h2><div class=\"grid\">{check_cards}</div></section>
    <section class=\"panel\"><h2>Blockers</h2><ul>{blockers}</ul></section>
    <section class=\"panel\"><h2>Next actions</h2><ul>{next_actions}</ul></section>
    <section class=\"panel\"><h2>Artifacts</h2><table>{artifacts}</table></section>
  </main>
</body>
</html>
"""


def build_maintainer_review_pack(
    *,
    out_dir: str | Path,
    root: str | Path = ".",
    dashboard_dir: str | Path = "maintainer_dashboard",
    evidence_dir: str | Path = "real_mac_evidence",
    launch_assets_dir: str | Path = "launch_assets",
    candidate_dir: str | Path = "public_alpha_candidate",
) -> MaintainerReviewPackReport:
    root_path = Path(root)
    out = Path(out_dir)
    if not out.is_absolute():
        out = root_path / out
    out.mkdir(parents=True, exist_ok=True)
    (out / "scripts").mkdir(exist_ok=True)

    commands = {
        "01_refresh_candidate_inputs": (
            f"PYTHONPATH=src python -m meeting_agent real-mac-evidence-collect --root . --evidence-dir {evidence_dir} --out-json {evidence_dir}/real_mac_evidence.json --out-md {evidence_dir}/real_mac_evidence.md || true\n"
            f"PYTHONPATH=src python -m meeting_agent launch-assets-pack --out-dir {launch_assets_dir}\n"
            f"PYTHONPATH=src python -m meeting_agent public-alpha-candidate-pack --out-dir {candidate_dir}"
        ),
        "02_build_dashboard": (
            f"PYTHONPATH=src python -m meeting_agent maintainer-dashboard --root . --dashboard-dir {dashboard_dir} --evidence-dir {evidence_dir} --launch-assets-dir {launch_assets_dir} --candidate-dir {candidate_dir}"
        ),
        "03_open_dashboard": (
            f"python - <<'PY'\nimport webbrowser\nwebbrowser.open('file:///' + __import__('pathlib').Path('{dashboard_dir}/maintainer_dashboard.html').resolve().as_posix())\nPY"
        ),
        "04_keep_publication_locked": (
            "PYTHONPATH=src python -m meeting_agent publication-gate --root .\n"
            "echo 'Publication must remain on hold until maintainer explicitly unlocks configs/publication_policy.json.'"
        ),
    }
    artifacts: dict[str, str] = {}
    for name, command in commands.items():
        path = out / "scripts" / f"{name}.sh"
        path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n\n" + command + "\n", encoding="utf-8")
        try:
            path.chmod(0o755)
        except OSError:
            pass
        artifacts[f"scripts/{path.name}"] = str(path)

    docs = {
        "README.md": _review_pack_readme(),
        "MAINTAINER_DECISION_MATRIX.md": _decision_matrix(),
        "EVIDENCE_DASHBOARD_GUIDE.md": _dashboard_guide(),
        "PUBLIC_UNLOCK_RISK_REVIEW.md": _risk_review(),
        "COMMANDS.md": _commands_doc(commands),
    }
    for rel, text in docs.items():
        path = out / rel
        path.write_text(text, encoding="utf-8")
        artifacts[rel] = str(path)

    manifest = {
        "schema_version": "maintainer-review-pack/v1",
        "project": "ai-meeting-agent-community",
        "version": __version__,
        "stage": "private_public_alpha_candidate_review",
        "publication_hold": True,
        "opens_microphone": False,
        "private_core_included": False,
        "dashboard_dir": str(dashboard_dir),
        "evidence_dir": str(evidence_dir),
        "launch_assets_dir": str(launch_assets_dir),
        "candidate_dir": str(candidate_dir),
        "generated_at": utc_now_iso(),
    }
    _write_json(out / "maintainer_review_manifest.json", manifest)
    artifacts["maintainer_review_manifest.json"] = str(out / "maintainer_review_manifest.json")

    checks = [
        MaintainerDashboardCheck("review_pack_created", "pass", "Maintainer review docs and scripts generated without opening microphone.", "pack", True),
        MaintainerDashboardCheck("publication_hold", "pass", "Review pack keeps publication locked by default.", "publication", True),
        MaintainerDashboardCheck("private_core_excluded", "pass", "Pack includes only Community/public-core review instructions.", "commercial_guardrail", True),
    ]
    report = MaintainerReviewPackReport(
        status="pass",
        score=1.0,
        out_dir=str(out),
        generated_at=utc_now_iso(),
        recommendation="Maintainer review pack is ready. Use it to refresh evidence, build the dashboard, and keep publication locked until real Mac evidence, local ASR smoke, screenshots, and maintainer approval are complete.",
        commands=commands,
        artifacts=artifacts,
        checks=checks,
        publication_hold=True,
        opens_microphone=False,
        private_core_included=False,
    )
    _write_json(out / "maintainer_review_pack.json", report.to_dict())
    (out / "maintainer_review_pack.md").write_text(report.to_markdown(), encoding="utf-8")
    return report


def build_maintainer_dashboard(
    *,
    root: str | Path = ".",
    dashboard_dir: str | Path = "maintainer_dashboard",
    evidence_dir: str | Path = "real_mac_evidence",
    launch_assets_dir: str | Path = "launch_assets",
    candidate_dir: str | Path = "public_alpha_candidate",
    demo_dir: str | Path = "demo_out",
    bridge_port: int = 8765,
    write_files: bool = True,
) -> MaintainerDashboardReport:
    root_path = Path(root)
    out = Path(dashboard_dir)
    if not out.is_absolute():
        out = root_path / out
    checks: list[MaintainerDashboardCheck] = []
    artifacts: dict[str, str] = {}

    publication = run_publication_gate(root=root_path)
    publication_hold = publication.status == "hold"
    checks.append(MaintainerDashboardCheck(
        "publication_gate",
        "pass" if publication_hold else "warn",
        f"publication-gate status={publication.status}",
        "publication",
        True,
        {"blocked_modes": publication.blocked_modes, "allowed_modes": publication.allowed_modes},
    ))

    release = run_release_readiness(root=root_path, profile="public_oss", run_tests=False)
    checks.append(MaintainerDashboardCheck("release_check", release.status, f"release-check score={release.score}", "release", True))

    public_alpha = run_public_alpha_readiness(root=root_path, bridge_port=bridge_port)
    checks.append(MaintainerDashboardCheck("public_alpha_readiness", public_alpha.status, public_alpha.recommendation, "public_alpha", True))

    candidate = run_public_alpha_candidate_gate(
        root=root_path,
        candidate_dir=candidate_dir,
        evidence_dir=evidence_dir,
        launch_assets_dir=launch_assets_dir,
        demo_dir=demo_dir,
        bridge_port=bridge_port,
    )
    checks.append(MaintainerDashboardCheck("public_alpha_candidate_gate", candidate.status, candidate.recommendation, "candidate", True))

    evidence = collect_real_mac_evidence(
        root=root_path,
        evidence_dir=evidence_dir,
        launch_assets_dir=launch_assets_dir,
        copy_artifacts=False,
    )
    checks.append(MaintainerDashboardCheck("real_mac_evidence", evidence.status, evidence.recommendation, "evidence", True, evidence.summary))
    artifacts.update({f"evidence:{k}": v for k, v in evidence.artifacts.items()})

    launch = run_launch_polish_check(root=root_path, launch_assets_dir=launch_assets_dir, demo_dir=demo_dir)
    checks.append(MaintainerDashboardCheck("launch_assets_gate", launch.status, launch.recommendation, "launch", True))
    artifacts.update({f"launch:{k}": v for k, v in launch.artifacts.items()})

    screenshot_count = _count_screenshots(root_path, evidence_dir, launch_assets_dir)
    checks.append(MaintainerDashboardCheck(
        "public_alpha_screenshots",
        "pass" if screenshot_count >= 3 else "warn",
        f"{screenshot_count} screenshot(s) found; 3+ recommended before public alpha.",
        "launch",
        True,
        {"screenshot_count": screenshot_count},
    ))

    private_core = _private_core_leak_detected(root_path)
    checks.append(MaintainerDashboardCheck(
        "private_core_excluded",
        "fail" if private_core else "pass",
        "Private-looking core directories were detected." if private_core else "No private quality-engine directories detected in public Community tree.",
        "commercial_guardrail",
        True,
    ))

    blockers: list[str] = []
    for check in checks:
        if check.status in {"fail", "error"}:
            blockers.append(f"{check.id}: {check.detail}")
    if publication_hold:
        blockers.append("publication_policy remains locked, by design, until maintainer approval.")
    if candidate.status.startswith("hold"):
        blockers.extend(candidate.blockers[:6])
    if evidence.status != "pass":
        blockers.append("real Mac evidence is incomplete: capture, ASR, minutes, or screenshots still need final collection.")
    if screenshot_count < 3:
        blockers.append("public alpha screenshot set is incomplete; collect at least 3 screenshots/GIF assets.")
    if private_core:
        blockers.append("private-core-looking path detected; remove it before any public repository operation.")

    pass_count = sum(1 for check in checks if check.status == "pass")
    score = round(pass_count / max(1, len(checks)), 2)
    if private_core:
        status = "blocked_private_core"
        decision = "do_not_publish"
    elif not publication_hold and evidence.status == "pass" and screenshot_count >= 3 and candidate.status in {"candidate_policy_unlocked_review_required", "candidate_ready_but_publication_hold"}:
        status = "candidate_review_ready"
        decision = "maintainer_review_required"
    else:
        status = "hold"
        decision = "keep_private"

    summary = {
        "version": __version__,
        "release_check": release.status,
        "publication_gate": publication.status,
        "public_alpha_readiness": public_alpha.status,
        "candidate_gate": candidate.status,
        "real_mac_evidence": evidence.status,
        "launch_assets": launch.status,
        "screenshots": screenshot_count,
        "checks_passed": pass_count,
        "checks_total": len(checks),
    }
    next_actions = [
        "Run the real Mac evidence pack on the maintainer Mac and collect mic_alpha_live, ASR, and screenshot artifacts.",
        "Run faster-whisper smoke on captured audio, then regenerate ASR→Minutes artifacts.",
        "Refresh launch assets and screenshots, then rerun maintainer-dashboard.",
        "Keep publication_policy.json locked until every required signal is reviewed and approved.",
    ]
    report = MaintainerDashboardReport(
        status=status,
        score=score,
        generated_at=utc_now_iso(),
        recommendation=_dashboard_recommendation(status, publication_hold, score),
        estimated_public_unlock="1-3 weeks if real Mac capture, faster-whisper smoke, screenshots, and README review pass",
        decision=decision,
        checks=checks,
        blockers=blockers,
        next_actions=next_actions,
        artifacts=artifacts,
        summary=summary,
        publication_hold=publication_hold,
        private_core_included=private_core,
    )
    if write_files:
        out.mkdir(parents=True, exist_ok=True)
        _write_json(out / "maintainer_dashboard.json", report.to_dict())
        (out / "maintainer_dashboard.md").write_text(report.to_markdown(), encoding="utf-8")
        (out / "maintainer_dashboard.html").write_text(report.to_html(), encoding="utf-8")
    return report


def write_maintainer_review_pack_report(report: MaintainerReviewPackReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        _write_json(Path(out_json), report.to_dict())
    if out_md:
        Path(out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(out_md).write_text(report.to_markdown(), encoding="utf-8")


def write_maintainer_dashboard_report(report: MaintainerDashboardReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None, out_html: str | Path | None = None) -> None:
    if out_json:
        _write_json(Path(out_json), report.to_dict())
    if out_md:
        Path(out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(out_md).write_text(report.to_markdown(), encoding="utf-8")
    if out_html:
        Path(out_html).parent.mkdir(parents=True, exist_ok=True)
        Path(out_html).write_text(report.to_html(), encoding="utf-8")


def _count_screenshots(root: Path, evidence_dir: str | Path, launch_assets_dir: str | Path) -> int:
    candidates = [
        root / evidence_dir / "screenshots",
        root / evidence_dir,
        root / launch_assets_dir / "screenshots",
        root / "screenshots",
    ]
    count = 0
    seen: set[Path] = set()
    for directory in candidates:
        if not directory.exists() or not directory.is_dir():
            continue
        for pattern in ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp"):
            for path in directory.glob(pattern):
                if path not in seen:
                    seen.add(path)
                    count += 1
    return count


def _private_core_leak_detected(root: Path) -> bool:
    risky_names = {"private_core", "quality_engine_private", "commercial_core", "private_evals", "enterprise_core"}
    for path in root.rglob("*"):
        if path.is_dir() and path.name.lower() in risky_names:
            return True
    return False


def _dashboard_recommendation(status: str, publication_hold: bool, score: float) -> str:
    if status == "blocked_private_core":
        return "Do not publish. A private-core-looking path was detected and must be removed before any external repository operation."
    if publication_hold:
        return "Keep the project private. The maintainer dashboard is useful for review, but publication_policy is intentionally locked until real Mac evidence, local ASR smoke, screenshots, and final README review pass."
    if status == "candidate_review_ready":
        return "Candidate looks ready for maintainer review, but final approval and rollback plan review are still required before public release."
    return f"Continue private review. Current dashboard score is {score}; complete the remaining evidence and launch checks before unlocking publication."


def _review_pack_readme() -> str:
    return """# Maintainer Review Pack

This private pack helps the maintainer review Public Alpha readiness without publishing anything.

It intentionally keeps publication locked and does not open the microphone. Use the scripts to refresh evidence, build the dashboard, and review blockers before any public repository or announcement decision.
"""


def _decision_matrix() -> str:
    return """# Maintainer Decision Matrix

| Signal | Publish decision |
|---|---|
| publication-gate = hold | Do not publish. This is the expected default. |
| real Mac evidence = warn | Continue private capture/ASR/screenshot validation. |
| screenshots < 3 | Continue launch asset collection. |
| private core included = true | Block immediately. Remove leaked private artifacts. |
| candidate gate ready + maintainer approval | Eligible for final unlock review. |
"""


def _dashboard_guide() -> str:
    return """# Evidence Dashboard Guide

Run:

```bash
PYTHONPATH=src python -m meeting_agent maintainer-dashboard --root . --dashboard-dir maintainer_dashboard
open maintainer_dashboard/maintainer_dashboard.html
```

Review status, blockers, next actions, and artifact references before changing publication policy.
"""


def _risk_review() -> str:
    return """# Public Unlock Risk Review

Before public alpha, confirm:

- No private quality-engine code is present.
- Recording consent and safety gates are documented.
- Limitations are explicit in README and launch notes.
- Evidence artifacts are reproducible on the maintainer Mac.
- Rollback/unpublish plan exists.
"""


def _commands_doc(commands: dict[str, str]) -> str:
    lines = ["# Maintainer Review Commands", ""]
    for name, command in commands.items():
        lines.extend([f"## {name}", "", "```bash", command, "```", ""])
    return "\n".join(lines)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _html(value: Any) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _safe_class(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value).lower())
