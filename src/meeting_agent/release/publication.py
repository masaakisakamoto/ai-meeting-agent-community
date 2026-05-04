from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from meeting_agent.core.schemas import utc_now_iso

PublicationStatus = Literal["hold", "ready", "needs_policy"]


@dataclass
class PublicationGateReport:
    project: str
    status: PublicationStatus
    score: float
    current_stage: str
    target_public_stage: str
    generated_at: str = field(default_factory=utc_now_iso)
    hold_reason: str = ""
    allowed_modes: list[str] = field(default_factory=list)
    blocked_modes: list[str] = field(default_factory=list)
    minimum_public_exit_criteria: list[str] = field(default_factory=list)
    policy_path: str = ""
    recommendation: str = ""
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Publication Gate",
            "",
            f"- Project: `{self.project}`",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Current stage: `{self.current_stage}`",
            f"- Target public stage: `{self.target_public_stage}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            f"- Policy: `{self.policy_path}`",
            f"- Generated at: `{self.generated_at}`",
            "",
            "## Recommendation",
            "",
            self.recommendation,
            "",
        ]
        if self.hold_reason:
            lines.extend(["## Hold reason", "", self.hold_reason, ""])
        lines.extend(["## Allowed modes", ""])
        lines.extend(f"- {mode}" for mode in self.allowed_modes)
        lines.extend(["", "## Blocked modes", ""])
        lines.extend(f"- {mode}" for mode in self.blocked_modes)
        lines.extend(["", "## Minimum public exit criteria", ""])
        lines.extend(f"- {item}" for item in self.minimum_public_exit_criteria)
        return "\n".join(lines) + "\n"


def load_publication_policy(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    policy_path = root_path / "configs" / "publication_policy.json"
    if not policy_path.exists():
        return {
            "schema_version": "publication-policy/missing",
            "project": root_path.name,
            "current_stage": "unknown",
            "public_oss_announcement_allowed": False,
            "target_public_stage": "public_alpha",
            "hold_reason": "configs/publication_policy.json is missing.",
            "allowed_modes": ["local_development"],
            "blocked_modes": ["public_github_repository", "sns_announcement"],
            "minimum_public_exit_criteria": ["Create configs/publication_policy.json"],
        }
    return json.loads(policy_path.read_text(encoding="utf-8"))


def run_publication_gate(root: str | Path) -> PublicationGateReport:
    root_path = Path(root).resolve()
    policy_path = root_path / "configs" / "publication_policy.json"
    policy = load_publication_policy(root_path)
    allowed = bool(policy.get("public_oss_announcement_allowed", False))
    if allowed:
        status: PublicationStatus = "ready"
        score = 1.0
        recommendation = "Public OSS announcement is allowed by policy. Re-run all gates immediately before publishing."
    elif policy_path.exists():
        status = "hold"
        score = 1.0
        recommendation = "Keep this repository private for now. Continue local development and controlled technical review only. Do not make a public GitHub repository or SNS announcement."
    else:
        status = "needs_policy"
        score = 0.0
        recommendation = "Create configs/publication_policy.json before making any publication decision."
    return PublicationGateReport(
        project=str(policy.get("project") or _project_name(root_path)),
        status=status,
        score=score,
        current_stage=str(policy.get("current_stage") or "unknown"),
        target_public_stage=str(policy.get("target_public_stage") or "public_alpha"),
        hold_reason=str(policy.get("hold_reason") or ""),
        allowed_modes=list(policy.get("allowed_modes") or []),
        blocked_modes=list(policy.get("blocked_modes") or []),
        minimum_public_exit_criteria=list(policy.get("minimum_public_exit_criteria") or []),
        policy_path=str(policy_path),
        recommendation=recommendation,
        private_core_included=False,
    )


def write_publication_gate_report(report: PublicationGateReport, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() == ".json":
        target.write_text(report.to_json() + "\n", encoding="utf-8")
    else:
        target.write_text(report.to_markdown(), encoding="utf-8")


def _project_name(root: Path) -> str:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return root.name
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("name"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return root.name
