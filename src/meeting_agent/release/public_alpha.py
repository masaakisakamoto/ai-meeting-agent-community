from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent.core.schemas import utc_now_iso
from meeting_agent.desktop.package_check import run_desktop_package_check
from meeting_agent.env.dev_environment import run_dev_environment_doctor
from meeting_agent.release.private_alpha import run_private_alpha_gate
from meeting_agent.release.publication import run_publication_gate
from meeting_agent.release.readiness import run_release_readiness
from meeting_agent.release.launch_assets import run_launch_polish_check


@dataclass(frozen=True)
class PublicAlphaCheck:
    id: str
    status: str
    detail: str
    category: str = "readiness"
    blocker: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublicAlphaMilestone:
    id: str
    title: str
    status: str
    estimate: str
    required_for_public_announcement: bool
    tasks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublicAlphaReadinessReport:
    status: str
    score: float
    generated_at: str
    recommendation: str
    estimated_time_to_public_announcement: str
    estimated_time_to_controlled_preview: str
    checks: list[PublicAlphaCheck]
    milestones: list[PublicAlphaMilestone]
    allowed_modes: list[str]
    blocked_modes: list[str]
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        payload["milestones"] = [milestone.to_dict() for milestone in self.milestones]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Public Alpha Readiness",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Controlled preview estimate: `{self.estimated_time_to_controlled_preview}`",
            f"- Public announcement estimate: `{self.estimated_time_to_public_announcement}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            f"- Generated at: `{self.generated_at}`",
            "",
            "## Recommendation",
            "",
            self.recommendation,
            "",
            "## Checks",
            "",
            "| Check | Status | Blocker | Category | Detail |",
            "|---|---|---:|---|---|",
        ]
        for check in self.checks:
            lines.append(
                f"| {check.id} | `{check.status}` | `{str(check.blocker).lower()}` | {check.category} | {_md(check.detail)} |"
            )
        lines.extend(["", "## Milestones", ""])
        for milestone in self.milestones:
            lines.extend([
                f"### {milestone.title}",
                "",
                f"- ID: `{milestone.id}`",
                f"- Status: `{milestone.status}`",
                f"- Estimate: `{milestone.estimate}`",
                f"- Required for public announcement: `{str(milestone.required_for_public_announcement).lower()}`",
                "",
            ])
            for task in milestone.tasks:
                lines.append(f"- {task}")
            lines.append("")
        lines.extend(["## Allowed modes", ""])
        lines.extend(f"- `{mode}`" for mode in self.allowed_modes)
        lines.extend(["", "## Blocked modes", ""])
        lines.extend(f"- `{mode}`" for mode in self.blocked_modes)
        lines.append("")
        return "\n".join(lines)


@dataclass(frozen=True)
class PublicAlphaPlanReport:
    status: str
    score: float
    generated_at: str
    next_version_goal: str
    strategy: str
    near_term_actions: list[str]
    launch_blockers: list[str]
    suggested_version_path: list[dict[str, Any]]
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Public Alpha Plan",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Next version goal: `{self.next_version_goal}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            f"- Generated at: `{self.generated_at}`",
            "",
            "## Strategy",
            "",
            self.strategy,
            "",
            "## Near-term actions",
            "",
        ]
        lines.extend(f"- {item}" for item in self.near_term_actions)
        lines.extend(["", "## Launch blockers", ""])
        lines.extend(f"- {item}" for item in self.launch_blockers)
        lines.extend(["", "## Suggested version path", ""])
        for item in self.suggested_version_path:
            lines.extend([
                f"### {item['version']}: {item['theme']}",
                "",
                f"- Exit criteria: {item['exit_criteria']}",
                f"- Estimate: {item['estimate']}",
                "",
            ])
        return "\n".join(lines)


def run_public_alpha_readiness(*, root: str | Path = ".", bridge_port: int = 8765) -> PublicAlphaReadinessReport:
    root_path = Path(root)
    checks: list[PublicAlphaCheck] = []

    release = run_release_readiness(root=root_path, profile="public_oss", run_tests=False)
    checks.append(PublicAlphaCheck("release_hygiene", _ok_or_fail(release.status), f"release-check status={release.status} score={release.score}", "code_quality", False, {"score": release.score}))

    publication = run_publication_gate(root_path)
    publication_on_hold = publication.status == "hold"
    checks.append(PublicAlphaCheck("publication_hold", "pass" if publication_on_hold else "fail", f"publication-gate status={publication.status}; public announcement remains intentionally blocked", "commercial_guardrail", False, {"blocked_modes": publication.blocked_modes}))

    private_alpha = run_private_alpha_gate(root=root_path, run_tests=False, bridge_port=bridge_port)
    checks.append(PublicAlphaCheck("private_alpha_gate", _ok_or_fail(private_alpha.status), f"private-alpha-gate status={private_alpha.status} score={private_alpha.score}", "private_alpha", False, {"score": private_alpha.score}))

    desktop = run_desktop_package_check(root_path)
    checks.append(PublicAlphaCheck("desktop_alpha_scaffold", _ok_or_fail(desktop.status), f"desktop-package-check status={desktop.status} score={desktop.score}", "desktop", False, {"score": desktop.score}))

    env = run_dev_environment_doctor(root=root_path, bridge_port=bridge_port)
    checks.append(PublicAlphaCheck("dev_environment", "pass" if env.status in {"pass", "warn"} else "fail", f"dev-env-doctor status={env.status} score={env.score}", "developer_experience", False, {"python_version": env.python_version, "score": env.score}))

    mic_live = _find_existing(root_path, ["mic_alpha_live/audio.wav", "demo_out/mic_alpha_live/audio.wav", "demo_out/microphone_alpha/audio.wav"])
    checks.append(PublicAlphaCheck(
        "mac_real_microphone_validation",
        "pass" if mic_live else "warn",
        "Real microphone WAV found." if mic_live else "No real microphone capture artifact found yet. This is the main launch blocker until your Mac hardware validation is complete.",
        "hardware_validation",
        blocker=not bool(mic_live),
        metadata={"expected_artifact": "mic_alpha_live/audio.wav", "found": str(mic_live) if mic_live else None},
    ))

    real_capture_gate = _find_existing(root_path, ["real_capture_execution_gate.json", "demo_out/real_capture_execution_gate.json", "mic_alpha_live/real_capture_execution_gate.json"])
    real_capture_gate_status = _read_json_status(real_capture_gate) if real_capture_gate else None
    checks.append(PublicAlphaCheck(
        "real_capture_execution_gate",
        "pass" if real_capture_gate_status == "pass" else ("warn" if real_capture_gate else "warn"),
        f"Real capture execution gate found with status={real_capture_gate_status}." if real_capture_gate else "No real-capture execution gate report found yet. Generate it after the live microphone validation run.",
        "hardware_validation",
        blocker=False,
        metadata={"found": str(real_capture_gate) if real_capture_gate else None, "status": real_capture_gate_status},
    ))

    mic_minutes = _find_existing(root_path, ["mic_minutes_live/minutes.html", "asr_minutes_faster_whisper/minutes.html", "demo_out/asr_minutes/minutes.html"])
    checks.append(PublicAlphaCheck(
        "real_audio_minutes_validation",
        "pass" if mic_minutes else "warn",
        "Real or deterministic audio minutes artifact found." if mic_minutes else "No live-capture minutes artifact found yet. Generate minutes from a real captured WAV before public announcement.",
        "workflow_validation",
        blocker=not bool(mic_minutes),
        metadata={"expected_artifact": "mic_minutes_live/minutes.html", "found": str(mic_minutes) if mic_minutes else None},
    ))

    real_asr_report = _find_existing(root_path, ["asr_minutes_faster_whisper/asr_minutes_report.json", "asr_validation_faster_whisper/asr_validation_report.json", "demo_out/asr_minutes_report.json"])
    checks.append(PublicAlphaCheck(
        "local_asr_validation",
        "pass" if real_asr_report else "warn",
        "ASR validation report found." if real_asr_report else "No local faster-whisper validation artifact found yet. Sidecar validation is useful, but public announcement should include one real ASR smoke.",
        "asr_validation",
        blocker=not bool(real_asr_report),
        metadata={"expected_artifact": "asr_minutes_faster_whisper/asr_minutes_report.json", "found": str(real_asr_report) if real_asr_report else None},
    ))

    local_smoke = _find_existing(root_path, ["local_asr_smoke/local_asr_smoke_report.json", "demo_out/local_asr_smoke_report.json", "demo_out/local_asr_smoke/local_asr_smoke_report.json"])
    local_smoke_status = _read_json_status(local_smoke) if local_smoke else None
    checks.append(PublicAlphaCheck(
        "local_asr_smoke_gate",
        "pass" if local_smoke_status in {"pass", "warn"} else "warn",
        f"Local ASR smoke report found with status={local_smoke_status}." if local_smoke else "No local ASR smoke report found yet. Generate local-asr-smoke-run after real capture/sidecar setup.",
        "asr_validation",
        blocker=False,
        metadata={"expected_artifact": "local_asr_smoke/local_asr_smoke_report.json", "found": str(local_smoke) if local_smoke else None, "status": local_smoke_status},
    ))

    launch_assets_dir = _find_existing(root_path, ["launch_assets", "demo_out/launch_assets"]) or root_path / "launch_assets"
    launch_gate = run_launch_polish_check(root=root_path, launch_assets_dir=launch_assets_dir, demo_dir="demo_out")
    checks.append(PublicAlphaCheck(
        "launch_assets_polish",
        "pass" if launch_gate.status == "pass" else "warn",
        f"Launch polish check status={launch_gate.status} score={launch_gate.score}.",
        "launch_assets",
        blocker=False,
        metadata={"score": launch_gate.score},
    ))

    installer = _find_existing(root_path, ["dist", "target/release", "apps/desktop-tauri/src-tauri/target/release"])
    checks.append(PublicAlphaCheck(
        "desktop_installer_or_packaged_app",
        "pass" if installer else "warn",
        "Packaged desktop app or build output found." if installer else "Desktop Alpha works, but native installer/package is not built yet.",
        "desktop_packaging",
        blocker=False,
        metadata={"found": str(installer) if installer else None},
    ))

    readme = root_path / "README.md"
    readme_text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    has_preview_label = "Developer Preview" in readme_text or "Private Developer Preview" in readme_text or "Desktop Alpha" in readme_text
    checks.append(PublicAlphaCheck(
        "public_readme_expectation_control",
        "pass" if has_preview_label else "warn",
        "README includes preview/alpha expectation-control language." if has_preview_label else "README should clearly state Desktop Alpha / Private Developer Preview limitations before public announcement.",
        "launch_assets",
        blocker=False,
    ))

    launch_polish = run_launch_polish_check(root=root_path, demo_dir="demo_out", launch_assets_dir="launch_assets")
    checks.append(PublicAlphaCheck(
        "launch_asset_polish",
        "pass" if launch_polish.status == "pass" else "warn",
        f"launch-polish-check status={launch_polish.status} score={launch_polish.score}; publication remains blocked until maintainer approval.",
        "launch_assets",
        blocker=False,
        metadata={"score": launch_polish.score, "missing": launch_polish.missing_or_warn_items},
    ))

    real_mac_evidence = _find_existing(root_path, ["real_mac_evidence/real_mac_evidence.json", "demo_out/real_mac_evidence.json", "demo_out/real_mac_evidence/evidence_index.json"])
    evidence_status = _read_json_status(real_mac_evidence) if real_mac_evidence else None
    checks.append(PublicAlphaCheck(
        "real_mac_evidence_collection",
        "pass" if evidence_status == "pass" else "warn",
        f"Real Mac evidence collection found with status={evidence_status}." if real_mac_evidence else "No real Mac evidence collection report found yet. Collect evidence after real capture, local ASR smoke, launch assets, and screenshots.",
        "launch_evidence",
        blocker=False,
        metadata={"expected_artifact": "real_mac_evidence/real_mac_evidence.json", "found": str(real_mac_evidence) if real_mac_evidence else None, "status": evidence_status},
    ))

    checks.append(PublicAlphaCheck("private_core_excluded", "pass", "Private Quality Engine is not included in the Community package.", "commercial_guardrail", False))

    milestones = build_public_alpha_milestones(checks)
    score = _score(checks)
    blocker_count = sum(1 for check in checks if check.blocker and check.status != "pass")
    if not publication_on_hold:
        status = "blocked"
    elif blocker_count:
        status = "hold"
    elif any(check.status == "warn" for check in checks):
        status = "ready_with_warnings_but_publication_hold"
    else:
        status = "candidate_but_publication_hold"

    return PublicAlphaReadinessReport(
        status=status,
        score=score,
        generated_at=utc_now_iso(),
        recommendation=_readiness_recommendation(status, blocker_count),
        estimated_time_to_controlled_preview="0-1 development sessions; already suitable for private/controlled technical review.",
        estimated_time_to_public_announcement=_estimate_public_timing(blocker_count),
        checks=checks,
        milestones=milestones,
        allowed_modes=["local_development", "private_repository", "private_portfolio_review", "controlled_technical_review", "private_alpha_hardware_validation"],
        blocked_modes=["public_github_repository", "sns_announcement", "commercial_landing_page", "public_release_blog"],
        private_core_included=False,
    )


def build_public_alpha_plan(*, root: str | Path = ".", bridge_port: int = 8765) -> PublicAlphaPlanReport:
    readiness = run_public_alpha_readiness(root=root, bridge_port=bridge_port)
    blockers = [check.detail for check in readiness.checks if check.blocker and check.status != "pass"]
    path = [
        {"version": "v1.6", "theme": "Real microphone validation execution pack and gate", "exit_criteria": "Execution pack and gate are available; Mac live capture still needs maintainer-side evidence.", "estimate": "implemented in this private preview."},
        {"version": "v1.7", "theme": "Local ASR smoke on captured audio", "exit_criteria": "Local ASR smoke pack/run/gate are implemented; Mac-side faster-whisper real smoke still needs evidence.", "estimate": "implemented in this private preview."},
        {"version": "v1.8", "theme": "Desktop packaging and launch asset polish", "exit_criteria": "Launch asset pack/gate, screenshot plan, demo script, macOS quickstart, limitations, and UI/Bridge launch controls are implemented; screenshots still need maintainer capture.", "estimate": "implemented in this private preview."},
        {"version": "v2.0", "theme": "Public Alpha announcement candidate", "exit_criteria": "Maintainer flips publication policy, re-runs all gates, and publishes with clear limitations.", "estimate": "1 release session after gates pass."},
    ]
    return PublicAlphaPlanReport(
        status="hold_plan_ready" if readiness.status != "blocked" else "blocked",
        score=readiness.score,
        generated_at=utc_now_iso(),
        next_version_goal="v1.9 Real Mac Evidence Collection",
        strategy="Do not publish yet. Continue private development until one real Mac microphone capture, one local-ASR smoke, and launch-readiness polish pass. Keep the publication gate on hold until the maintainer explicitly flips the policy.",
        near_term_actions=[
            "Install/use Python 3.12 virtual environment for audio dependencies.",
            "Use the v1.6 real-capture execution pack, then run live microphone capture for 3 seconds with explicit consent flags.",
            "Run post-capture gate and microphone-to-minutes on the captured WAV.",
            "Run local-asr-smoke-run with sidecar first, then faster-whisper smoke if dependencies are ready.",
            "Launch-assets-pack and launch-polish-check are now available; replace screenshot placeholders after local validation.",
            "Generate launch-assets-pack and capture the planned screenshots privately.",
            "Keep public repository/SNS/LP/blog blocked until all public alpha blockers clear.",
        ],
        launch_blockers=blockers or ["No hard launch blockers detected, but publication policy is intentionally on hold."],
        suggested_version_path=path,
        private_core_included=False,
    )


def write_public_alpha_readiness_report(report: PublicAlphaReadinessReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def write_public_alpha_plan_report(report: PublicAlphaPlanReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def build_public_alpha_milestones(checks: list[PublicAlphaCheck]) -> list[PublicAlphaMilestone]:
    statuses = {check.id: check.status for check in checks}
    return [
        PublicAlphaMilestone(
            id="m1_private_foundation",
            title="Private foundation remains healthy",
            status="pass" if statuses.get("release_hygiene") == "pass" and statuses.get("private_alpha_gate") == "pass" else "warn",
            estimate="already mostly complete",
            required_for_public_announcement=True,
            tasks=["Keep release-check passing.", "Keep publication-gate on hold until final decision.", "Keep private-core scan passing."],
        ),
        PublicAlphaMilestone(
            id="m2_real_capture",
            title="Real microphone capture validation",
            status=statuses.get("mac_real_microphone_validation", "warn"),
            estimate="1-2 focused sessions after Mac access",
            required_for_public_announcement=True,
            tasks=["Run 3-second live capture with consent flags.", "Validate audio.wav, audit.jsonl, and recording_safety_gate.", "Run capture-validation-run."],
        ),
        PublicAlphaMilestone(
            id="m3_local_asr",
            title="Local ASR smoke on captured audio",
            status=statuses.get("local_asr_validation", "warn"),
            estimate="1-3 sessions depending on faster-whisper setup",
            required_for_public_announcement=True,
            tasks=["Run local-asr-smoke-run with sidecar first.", "Run faster-whisper smoke on CPU or local accelerator.", "Run ASR-to-minutes and inspect HTML output."],
        ),
        PublicAlphaMilestone(
            id="m4_launch_assets",
            title="Public launch assets and packaging",
            status="warn" if statuses.get("desktop_installer_or_packaged_app") != "pass" else "pass",
            estimate="2-4 sessions",
            required_for_public_announcement=True,
            tasks=["Polish README screenshots and limitations.", "Add install/run docs for macOS.", "Prepare demo video or GIF.", "Optional: produce native desktop package."],
        ),
    ]


def _ok_or_fail(status: str) -> str:
    return "pass" if status in {"pass", "ready", "ready_with_warnings", "portfolio_preview_ready", "warn"} else "fail"


def _find_existing(root: Path, relative_candidates: list[str]) -> Path | None:
    for rel in relative_candidates:
        path = root / rel
        if path.exists():
            return path
    return None



def _read_json_status(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return str(payload.get("status") or payload.get("workflow", {}).get("status") or "")


def _score(checks: list[PublicAlphaCheck]) -> float:
    score = 1.0
    for check in checks:
        if check.status == "warn":
            score -= 0.08 if not check.blocker else 0.14
        elif check.status == "fail":
            score -= 0.25 if not check.blocker else 0.35
    return round(max(0.0, score), 3)


def _readiness_recommendation(status: str, blocker_count: int) -> str:
    if status == "candidate_but_publication_hold":
        return "Public Alpha criteria are effectively met, but publication is intentionally blocked by policy. Publish only after explicit maintainer approval."
    if status == "ready_with_warnings_but_publication_hold":
        return "Close the remaining warnings, then keep publication blocked until the maintainer intentionally flips the policy."
    if blocker_count:
        return f"Keep private. {blocker_count} launch blocker(s) remain, mainly real hardware capture and/or local ASR validation."
    return "Keep private until publication policy is intentionally changed."


def _estimate_public_timing(blocker_count: int) -> str:
    if blocker_count >= 3:
        return "2-4 weeks at the current pace; fastest path is real Mac microphone validation + local ASR smoke + launch asset polish."
    if blocker_count >= 1:
        return "1-2 weeks if real capture and local ASR pass quickly; otherwise 2-4 weeks."
    return "Several days to 1 week for final polish, screenshots, docs, and maintainer approval."


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
