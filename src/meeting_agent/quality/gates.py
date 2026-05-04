from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from meeting_agent.core.schemas import MinutesDraft, Transcript, VerificationReport


@dataclass(frozen=True)
class QualityGateCheck:
    id: str
    status: str
    severity: str
    message: str


@dataclass(frozen=True)
class QualityGateResult:
    status: str
    score: float
    checks: list[QualityGateCheck] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def run_minutes_quality_gate(
    transcript: Transcript,
    minutes: MinutesDraft,
    verification: VerificationReport,
    *,
    min_verification_score: float = 0.8,
    min_evidence_coverage: float = 0.95,
) -> QualityGateResult:
    """Run deterministic quality gates for minutes.

    The goal is not to judge semantic perfection. It ensures the Community engine
    maintains the product's most important contract: important claims must be
    grounded in transcript evidence and be reviewable.
    """

    checks: list[QualityGateCheck] = []

    checks.append(
        QualityGateCheck(
            id="transcript:has_segments",
            status="pass" if transcript.segments else "fail",
            severity="critical",
            message=f"Transcript segment count: {len(transcript.segments)}.",
        )
    )

    generated_items = _generated_items(minutes)
    checks.append(
        QualityGateCheck(
            id="minutes:has_generated_items",
            status="pass" if generated_items else "warn",
            severity="important",
            message=f"Generated item count: {len(generated_items)}.",
        )
    )

    coverage = _evidence_coverage(generated_items)
    checks.append(
        QualityGateCheck(
            id="minutes:evidence_coverage",
            status="pass" if coverage >= min_evidence_coverage else "fail" if coverage < 0.5 else "warn",
            severity="critical",
            message=f"Evidence coverage is {coverage:.3f}; required >= {min_evidence_coverage:.3f}.",
        )
    )

    checks.append(
        QualityGateCheck(
            id="verification:score",
            status="pass" if verification.score >= min_verification_score else "fail",
            severity="critical",
            message=f"Verification score is {verification.score:.3f}; required >= {min_verification_score:.3f}.",
        )
    )

    high_issues = [issue for issue in verification.issues if issue.severity == "high"]
    checks.append(
        QualityGateCheck(
            id="verification:no_high_severity_issues",
            status="pass" if not high_issues else "fail",
            severity="critical",
            message=f"High severity issue count: {len(high_issues)}.",
        )
    )

    weak_items = [item for item in generated_items if getattr(item, "confidence", 1.0) < 0.5]
    checks.append(
        QualityGateCheck(
            id="minutes:no_very_low_confidence_items",
            status="pass" if not weak_items else "warn",
            severity="important",
            message=f"Very low confidence generated item count: {len(weak_items)}.",
        )
    )

    score = _score(checks)
    has_critical_fail = any(c.severity == "critical" and c.status == "fail" for c in checks)
    has_warn = any(c.status == "warn" for c in checks)
    if has_critical_fail:
        status = "fail"
    elif has_warn:
        status = "needs_review"
    else:
        status = "pass"
    return QualityGateResult(status=status, score=round(score, 3), checks=checks)


def render_quality_gate_markdown(result: QualityGateResult) -> str:
    lines = ["# Minutes Quality Gate", ""]
    lines.append(f"- Status: `{result.status}`")
    lines.append(f"- Score: `{result.score}`")
    lines.append("")
    lines.append("| Status | Severity | Check | Message |")
    lines.append("|---|---|---|---|")
    for check in result.checks:
        message = check.message.replace("|", "\\|")
        lines.append(f"| {check.status} | {check.severity} | `{check.id}` | {message} |")
    return "\n".join(lines).rstrip() + "\n"


def write_quality_gate_result(result: QualityGateResult, out: str | Path) -> None:
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() == ".json":
        out_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        out_path.write_text(render_quality_gate_markdown(result), encoding="utf-8")


def _generated_items(minutes: MinutesDraft) -> list[object]:
    return [*minutes.decisions, *minutes.action_items, *minutes.open_questions, *minutes.risks]


def _evidence_coverage(items: Sequence[object]) -> float:
    if not items:
        return 1.0
    grounded = 0
    for item in items:
        evidence_ids = getattr(item, "evidence_segment_ids", [])
        if evidence_ids:
            grounded += 1
    return grounded / len(items)


def _score(checks: Sequence[QualityGateCheck]) -> float:
    weights = {"critical": 3.0, "important": 2.0, "advisory": 1.0}
    status_score = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
    total = 0.0
    earned = 0.0
    for check in checks:
        weight = weights.get(check.severity, 1.0)
        total += weight
        earned += weight * status_score.get(check.status, 0.0)
    return earned / total if total else 0.0
