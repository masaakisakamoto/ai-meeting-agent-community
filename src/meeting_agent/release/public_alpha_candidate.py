from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent import __version__
from meeting_agent.core.schemas import utc_now_iso
from meeting_agent.release.launch_assets import run_launch_polish_check
from meeting_agent.release.public_alpha import run_public_alpha_readiness
from meeting_agent.release.publication import run_publication_gate
from meeting_agent.release.readiness import run_release_readiness


@dataclass(frozen=True)
class CandidateCheck:
    id: str
    status: str
    detail: str
    category: str = "candidate"
    required_for_public_alpha: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublicAlphaCandidatePackReport:
    status: str
    score: float
    out_dir: str
    generated_at: str
    recommendation: str
    commands: dict[str, str]
    artifacts: dict[str, str]
    checks: list[CandidateCheck]
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
            "# Public Alpha Candidate Pack",
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
class PublicAlphaCandidateGateReport:
    status: str
    score: float
    generated_at: str
    recommendation: str
    estimated_public_unlock: str
    checks: list[CandidateCheck]
    blockers: list[str]
    next_actions: list[str]
    allowed_modes: list[str]
    blocked_modes: list[str]
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
            "# Public Alpha Candidate Gate",
            "",
            f"- Status: `{self.status}`",
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
            "## Checks",
            "",
            "| Check | Status | Required | Category | Detail |",
            "|---|---|---:|---|---|",
        ]
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | `{str(check.required_for_public_alpha).lower()}` | {check.category} | {_md(check.detail)} |")
        if self.blockers:
            lines.extend(["", "## Blockers", ""])
            lines.extend(f"- {item}" for item in self.blockers)
        lines.extend(["", "## Next actions", ""])
        lines.extend(f"- {item}" for item in self.next_actions)
        lines.extend(["", "## Allowed modes", ""])
        lines.extend(f"- `{mode}`" for mode in self.allowed_modes)
        lines.extend(["", "## Blocked modes", ""])
        lines.extend(f"- `{mode}`" for mode in self.blocked_modes)
        lines.append("")
        return "\n".join(lines)


def build_public_alpha_candidate_pack(
    *,
    out_dir: str | Path,
    root: str | Path = ".",
    demo_dir: str | Path = "demo_out",
    evidence_dir: str | Path = "real_mac_evidence",
    launch_assets_dir: str | Path = "launch_assets",
    candidate_version: str = "v2.2 Public Alpha Candidate",
) -> PublicAlphaCandidatePackReport:
    """Generate a private candidate pack. It does not publish anything."""
    root_path = Path(root)
    out = Path(out_dir)
    if not out.is_absolute():
        out = root_path / out
    out.mkdir(parents=True, exist_ok=True)
    (out / "scripts").mkdir(exist_ok=True)

    commands = {
        "01_run_final_private_gates": (
            "PYTHONPATH=src python -m meeting_agent release-check --root . --out-json release_check.json --out-md release_check.md\n"
            "PYTHONPATH=src python -m meeting_agent publication-gate --root . --out-json publication_gate.json --out-md publication_gate.md\n"
            "PYTHONPATH=src python -m meeting_agent public-alpha-readiness --root . --out-json public_alpha_readiness.json --out-md public_alpha_readiness.md\n"
            "PYTHONPATH=src python -m meeting_agent public-alpha-candidate-gate --root . --candidate-dir public_alpha_candidate --out-json public_alpha_candidate_gate.json --out-md public_alpha_candidate_gate.md"
        ),
        "02_collect_real_mac_evidence": (
            f"PYTHONPATH=src python -m meeting_agent real-mac-evidence-collect --root . --evidence-dir {evidence_dir} --out-json real_mac_evidence.json --out-md real_mac_evidence.md"
        ),
        "03_refresh_launch_assets": (
            f"PYTHONPATH=src python -m meeting_agent launch-assets-pack --out-dir {launch_assets_dir}\n"
            f"PYTHONPATH=src python -m meeting_agent launch-assets-gate --assets-dir {launch_assets_dir} --demo-dir {demo_dir} --out-json launch_assets_gate.json --out-md launch_assets_gate.md"
        ),
        "04_maintainer_unlock_dry_run": (
            "echo 'Do not publish yet. First confirm real Mac evidence, faster-whisper smoke, screenshots, README, and maintainer approval.'\n"
            "echo 'Only after approval, edit configs/publication_policy.json and flip public_oss_announcement_allowed to true.'"
        ),
    }
    artifacts: dict[str, str] = {}
    for name, command in commands.items():
        script = out / "scripts" / f"{name}.sh"
        script.write_text("#!/usr/bin/env bash\nset -euo pipefail\n\n" + command + "\n", encoding="utf-8")
        try:
            script.chmod(0o755)
        except OSError:
            pass
        artifacts[f"scripts/{script.name}"] = str(script)

    docs = {
        "PUBLIC_ALPHA_CANDIDATE_README.md": _candidate_readme(candidate_version),
        "FINAL_PUBLICATION_UNLOCK_CHECKLIST.md": _unlock_checklist(),
        "CANDIDATE_RELEASE_NOTES.md": _candidate_release_notes(),
        "MAINTAINER_APPROVAL_TEMPLATE.md": _maintainer_approval_template(),
        "ROLLBACK_AND_UNPUBLISH_PLAN.md": _rollback_plan(),
        "SECURITY_PRIVACY_FINAL_REVIEW.md": _security_privacy_review(),
        "COMMANDS.md": _commands_doc(commands),
    }
    for rel, text in docs.items():
        path = out / rel
        path.write_text(text, encoding="utf-8")
        artifacts[rel] = str(path)

    manifest = {
        "schema_version": "public-alpha-candidate/v1",
        "project": "ai-meeting-agent-community",
        "version": __version__,
        "candidate_version": candidate_version,
        "stage": "private_developer_preview",
        "publication_hold": True,
        "opens_microphone": False,
        "private_core_included": False,
        "root": str(root_path),
        "demo_dir": str(demo_dir),
        "evidence_dir": str(evidence_dir),
        "launch_assets_dir": str(launch_assets_dir),
        "generated_at": utc_now_iso(),
    }
    _write_json(out / "public_alpha_candidate_manifest.json", manifest)
    artifacts["public_alpha_candidate_manifest.json"] = str(out / "public_alpha_candidate_manifest.json")

    checks = [
        CandidateCheck("candidate_pack_created", "pass", "Candidate docs and scripts generated without opening the microphone.", "pack", True),
        CandidateCheck("publication_hold", "pass", "Candidate pack intentionally keeps public publication blocked.", "publication", True),
        CandidateCheck("private_core_excluded", "pass", "Pack contains only public Community workflow instructions and no private quality engine.", "commercial_guardrail", True),
    ]
    report = PublicAlphaCandidatePackReport(
        status="pass",
        score=1.0,
        out_dir=str(out),
        generated_at=utc_now_iso(),
        recommendation="Candidate pack is ready for private maintainer review. Keep publication-gate on hold until real Mac evidence, local ASR smoke, screenshots, README review, and explicit maintainer approval are complete.",
        commands=commands,
        artifacts=artifacts,
        checks=checks,
        publication_hold=True,
        opens_microphone=False,
        private_core_included=False,
    )
    write_public_alpha_candidate_pack_report(report, out_json=out / "public_alpha_candidate_pack.json", out_md=out / "public_alpha_candidate_pack.md")
    return report


def run_public_alpha_candidate_gate(
    *,
    root: str | Path = ".",
    candidate_dir: str | Path = "public_alpha_candidate",
    evidence_dir: str | Path = "real_mac_evidence",
    launch_assets_dir: str | Path = "launch_assets",
    demo_dir: str | Path = "demo_out",
    bridge_port: int = 8765,
) -> PublicAlphaCandidateGateReport:
    root_path = Path(root)
    candidate_path = _resolve(root_path, candidate_dir)
    evidence_path = _resolve(root_path, evidence_dir)
    launch_path = _resolve(root_path, launch_assets_dir)
    checks: list[CandidateCheck] = []

    publication = run_publication_gate(root_path)
    publication_hold = publication.status == "hold"
    checks.append(CandidateCheck("publication_policy_hold", "pass" if publication_hold else "warn", f"publication-gate status={publication.status}; public release remains blocked until maintainer unlock.", "publication", True, {"blocked_modes": publication.blocked_modes}))

    release = run_release_readiness(root=root_path, profile="public_oss", run_tests=False)
    checks.append(CandidateCheck("release_check", "pass" if release.status == "pass" else "warn", f"release-check status={release.status} score={release.score}", "code_quality", True, {"score": release.score}))

    readiness = run_public_alpha_readiness(root=root_path, bridge_port=bridge_port)
    checks.append(CandidateCheck("public_alpha_readiness", "pass" if readiness.status in {"hold", "ready_with_warnings_but_publication_hold", "candidate_but_publication_hold"} else "warn", f"public-alpha-readiness status={readiness.status} score={readiness.score}", "readiness", True, {"score": readiness.score}))

    pack_manifest = candidate_path / "public_alpha_candidate_manifest.json"
    checks.append(CandidateCheck("candidate_pack_manifest", "pass" if pack_manifest.exists() else "warn", "Candidate manifest is present." if pack_manifest.exists() else "Candidate pack manifest missing. Run public-alpha-candidate-pack first.", "candidate_pack", True, {"path": str(pack_manifest)}))

    evidence_report = evidence_path / "real_mac_evidence.json"
    evidence_status = _read_status(evidence_report)
    checks.append(CandidateCheck("real_mac_evidence_collection", "pass" if evidence_status == "pass" else "warn", f"Real Mac evidence status={evidence_status}." if evidence_report.exists() else "Real Mac evidence collection missing or incomplete.", "hardware_evidence", True, {"path": str(evidence_report), "status": evidence_status}))

    launch = run_launch_polish_check(root=root_path, launch_assets_dir=launch_path, demo_dir=demo_dir)
    checks.append(CandidateCheck("launch_assets_gate", "pass" if launch.status == "pass" else "warn", f"launch-assets-gate status={launch.status} score={launch.score}", "launch_assets", True, {"score": launch.score}))

    screenshots = [root_path / "screenshots", root_path / "docs" / "images", _resolve(root_path, demo_dir) / "screenshots", evidence_path / "screenshots"]
    screenshot_count = sum(1 for base in screenshots if base.exists() for child in base.iterdir() if child.is_file())
    checks.append(CandidateCheck("public_alpha_screenshots", "pass" if screenshot_count >= 3 else "warn", f"Screenshot count={screenshot_count}. Need at least 3 launch-quality screenshots before public announcement.", "launch_assets", True, {"count": screenshot_count}))

    private_core = _private_core_scan(root_path)
    checks.append(CandidateCheck("private_core_excluded", "pass" if not private_core else "fail", "No private-core-looking directories found." if not private_core else "Private-core-looking paths found; do not publish.", "commercial_guardrail", True, {"paths": private_core}))

    blockers = [check.id for check in checks if check.required_for_public_alpha and check.status != "pass"]
    score = round(sum(1 for c in checks if c.status == "pass") / max(1, len(checks)), 3)
    if not publication_hold:
        status = "candidate_policy_unlocked_review_required"
        recommendation = "Publication policy appears unlocked. Perform one final maintainer review before publishing."
        estimated = "0-3 days after maintainer review"
    elif blockers:
        status = "hold_missing_candidate_evidence"
        recommendation = "Keep repository private. Finish the listed blockers, then rerun public-alpha-candidate-gate."
        estimated = "1-3 weeks depending on real Mac capture, ASR smoke, and screenshots"
    else:
        status = "candidate_ready_but_publication_hold"
        recommendation = "Candidate evidence is ready, but publication_policy still intentionally blocks public release. Maintainer can unlock only after deliberate approval."
        estimated = "0-3 days after explicit maintainer approval"

    next_actions = _next_actions(blockers, publication_hold)
    return PublicAlphaCandidateGateReport(
        status=status,
        score=score,
        generated_at=utc_now_iso(),
        recommendation=recommendation,
        estimated_public_unlock=estimated,
        checks=checks,
        blockers=blockers,
        next_actions=next_actions,
        allowed_modes=publication.allowed_modes,
        blocked_modes=publication.blocked_modes if publication_hold else [],
        publication_hold=publication_hold,
        private_core_included=bool(private_core),
    )


def write_public_alpha_candidate_pack_report(report: PublicAlphaCandidatePackReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        Path(out_json).write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        Path(out_md).write_text(report.to_markdown(), encoding="utf-8")


def write_public_alpha_candidate_gate_report(report: PublicAlphaCandidateGateReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        Path(out_json).write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        Path(out_md).write_text(report.to_markdown(), encoding="utf-8")


def _candidate_readme(candidate_version: str) -> str:
    return f"""# {candidate_version}

This is a **private candidate pack** for AI Meeting Agent Community. It is not a public release artifact.

Current policy:

- Public GitHub repository: blocked until maintainer approval
- SNS announcement: blocked until maintainer approval
- Commercial landing page: blocked until maintainer approval
- Private core: excluded

Use this pack to review whether the project is ready for a public alpha announcement after real Mac capture, local ASR smoke, launch screenshots, and final README review are complete.
"""


def _unlock_checklist() -> str:
    return """# Final Publication Unlock Checklist

Do not unlock publication until every item is checked:

- [ ] `release-check` passes.
- [ ] `public-alpha-readiness` is no worse than candidate-with-hold.
- [ ] Real Mac microphone capture evidence is collected.
- [ ] Local ASR smoke on captured audio is collected.
- [ ] Evidence-linked minutes HTML is generated from captured audio.
- [ ] At least 3 screenshots/GIF assets are prepared.
- [ ] README, Known Limitations, FAQ, and Release Notes are reviewed.
- [ ] Private-core leakage scan passes.
- [ ] Maintainer explicitly approves public release.
- [ ] Only then flip `public_oss_announcement_allowed` in `configs/publication_policy.json`.
"""


def _candidate_release_notes() -> str:
    return """# Candidate Release Notes Draft

AI Meeting Agent Community v2.2 Public Alpha Candidate focuses on a local-first, evidence-linked meeting intelligence workflow.

Included Community capabilities:

- Desktop Alpha UI and Local Bridge
- Safe-by-default microphone alpha guardrails
- Post-capture microphone-to-minutes workflow
- ASR validation and ASR-to-minutes workflow
- Real Mac evidence collection workflow
- Launch assets and public-alpha readiness gates

Not included:

- Private Quality Engine
- Production model router
- Private evaluation data
- Enterprise admin / SSO / billing modules
"""


def _maintainer_approval_template() -> str:
    return """# Maintainer Approval Template

I confirm that I reviewed the following before public release:

- Real Mac evidence collection
- Local ASR smoke evidence
- Launch screenshots and demo script
- README and Known Limitations
- Publication policy and private-core boundary

Approval decision:

- [ ] Keep private
- [ ] Controlled technical review only
- [ ] Public Alpha announcement approved

Maintainer:
Date:
Notes:
"""


def _rollback_plan() -> str:
    return """# Rollback and Unpublish Plan

If the public alpha announcement exposes a problem:

1. Stop new announcements.
2. Archive or make the repository private if necessary.
3. Remove generated artifacts that include accidental sensitive data.
4. Open a security/private-core incident if leakage is suspected.
5. Restore `publication_policy.json` to hold.
6. Publish a correction only after the issue is understood.
"""


def _security_privacy_review() -> str:
    return """# Security and Privacy Final Review

Before public alpha:

- Confirm no audio recordings are committed.
- Confirm no private API keys or secrets are committed.
- Confirm private-core directories are absent.
- Confirm recording notice and consent docs exist.
- Confirm README does not overclaim production readiness.
- Confirm optional microphone and ASR dependencies are clearly documented.
"""


def _commands_doc(commands: dict[str, str]) -> str:
    lines = ["# Candidate Commands", ""]
    for name, command in commands.items():
        lines.extend([f"## {name}", "", "```bash", command, "```", ""])
    return "\n".join(lines)


def _next_actions(blockers: list[str], publication_hold: bool) -> list[str]:
    mapping = {
        "candidate_pack_manifest": "Run `public-alpha-candidate-pack --out-dir public_alpha_candidate`.",
        "real_mac_evidence_collection": "Run the real Mac evidence scripts after live microphone capture and local ASR smoke.",
        "launch_assets_gate": "Generate and review launch assets with `launch-assets-pack` and `launch-assets-gate`.",
        "public_alpha_screenshots": "Capture at least 3 launch-quality screenshots or GIFs.",
        "private_core_excluded": "Remove any private-core-looking paths before release.",
    }
    actions = [mapping.get(item, f"Resolve blocker `{item}`.") for item in blockers]
    if publication_hold:
        actions.append("Keep publication_policy on hold until all blockers are pass and maintainer approval is explicit.")
    else:
        actions.append("Publication policy is unlocked; do a final manual review before public release.")
    return actions


def _private_core_scan(root: Path) -> list[str]:
    suspects = []
    patterns = ["private_core", "quality_engine_private", "enterprise_admin", "private_evals", "commercial_modules"]
    for path in root.rglob("*"):
        if any(part in path.name.lower() for part in patterns):
            # Keep docs that explain boundaries; only real dirs/files with suspect names are flagged.
            if path.is_dir() or path.suffix in {".py", ".json", ".env"}:
                suspects.append(str(path.relative_to(root)))
    return suspects[:20]


def _read_status(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload.get("status") or payload.get("workflow", {}).get("status")


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _md(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")
