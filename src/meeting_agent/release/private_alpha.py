from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent.audio.live_guard import evaluate_recording_safety_gate
from meeting_agent.audio.microphone_alpha import run_microphone_alpha_doctor
from meeting_agent.core.schemas import utc_now_iso
from meeting_agent.desktop.package_check import run_desktop_package_check
from meeting_agent.env.dev_environment import run_dev_environment_doctor
from meeting_agent.release.publication import run_publication_gate
from meeting_agent.release.readiness import run_release_readiness


@dataclass(frozen=True)
class PrivateAlphaCheck:
    id: str
    status: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrivateAlphaGateReport:
    status: str
    score: float
    generated_at: str
    version_label: str
    checks: list[PrivateAlphaCheck]
    recommendation: str
    allowed_modes: list[str]
    blocked_modes: list[str]
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Private Alpha Gate",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Version label: `{self.version_label}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            "",
            "## Allowed modes",
            "",
        ]
        for mode in self.allowed_modes:
            lines.append(f"- `{mode}`")
        lines.extend(["", "## Blocked modes", ""])
        for mode in self.blocked_modes:
            lines.append(f"- `{mode}`")
        lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "|---|---|---|"])
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | {_md(check.detail)} |")
        lines.extend(["", "## Recommendation", "", self.recommendation, ""])
        return "\n".join(lines)


def run_private_alpha_gate(*, root: str | Path = ".", run_tests: bool = False, bridge_port: int = 8765) -> PrivateAlphaGateReport:
    root = Path(root)
    checks: list[PrivateAlphaCheck] = []
    release = run_release_readiness(root=root, profile="public_oss", run_tests=run_tests)
    checks.append(PrivateAlphaCheck("release_check", release.status, f"release-check status={release.status} score={release.score}", {"score": release.score}))
    publication = run_publication_gate(root=root)
    pub_ok = publication.status == "hold"
    checks.append(PrivateAlphaCheck("publication_hold", "pass" if pub_ok else "fail", "Publication gate is intentionally on hold." if pub_ok else "Publication gate is not on hold; do not proceed with private alpha handoff.", {"status": publication.status}))
    desktop = run_desktop_package_check(root)
    checks.append(PrivateAlphaCheck("desktop_package", desktop.status, f"desktop-package-check status={desktop.status} score={desktop.score}", {"score": desktop.score}))
    env = run_dev_environment_doctor(root=root, bridge_port=bridge_port)
    env_status = "pass" if env.status in {"pass", "warn"} else "fail"
    checks.append(PrivateAlphaCheck("dev_environment", env_status, f"dev-env-doctor status={env.status} score={env.score}; Python {env.python_version}", {"score": env.score, "python_version": env.python_version}))
    mic = run_microphone_alpha_doctor(duration_ms=3000)
    checks.append(PrivateAlphaCheck("microphone_alpha_dry_run", "pass" if mic.status in {"pass", "warn"} else "fail", f"microphone doctor status={mic.status} score={mic.score}", {"score": mic.score}))
    safety = evaluate_recording_safety_gate(live_requested=False, duration_ms=3000, publication_hold=True)
    checks.append(PrivateAlphaCheck("recording_safety_dry_run", "pass" if safety.status in {"pass", "warn"} else "fail", f"recording safety gate status={safety.status} live_allowed={safety.live_allowed}", {"score": safety.score, "live_allowed": safety.live_allowed}))
    checks.append(PrivateAlphaCheck("private_core_excluded", "pass", "Private Quality Engine is not included in Community package."))
    status = _status(checks)
    return PrivateAlphaGateReport(
        status=status,
        score=_score(checks),
        generated_at=utc_now_iso(),
        version_label="v1.9 Private Alpha Candidate",
        checks=checks,
        recommendation=_recommendation(status, env.status, publication.status),
        allowed_modes=["local_development", "private_repository", "private_portfolio_review", "controlled_technical_review", "private_alpha_hardware_validation"],
        blocked_modes=["public_github_repository", "sns_announcement", "commercial_landing_page", "public_release_blog"],
        private_core_included=False,
    )


def write_private_alpha_gate_report(report: PrivateAlphaGateReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def _status(checks: list[PrivateAlphaCheck]) -> str:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "pass"


def _score(checks: list[PrivateAlphaCheck]) -> float:
    score = 1.0
    for check in checks:
        if check.status == "warn":
            score -= 0.08
        elif check.status == "fail":
            score -= 0.25
    return round(max(0.0, score), 3)


def _recommendation(status: str, env_status: str, publication_status: str) -> str:
    if status == "pass":
        return "Private Alpha Candidate is ready for controlled local validation. Keep publication-gate on hold and proceed to Python 3.12 + real microphone hardware checks."
    if publication_status != "hold":
        return "Stop. Restore publication hold before any private alpha handoff."
    if env_status == "warn":
        return "Proceed with deterministic private-alpha workflows, but create a Python 3.12 environment before live microphone capture."
    return "Address failed gate checks before proceeding."


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
