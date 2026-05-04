from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent.core.schemas import utc_now_iso

LIVE_CONFIRMATION_PHRASE = "I_UNDERSTAND_THIS_RECORDS_AUDIO"
MAX_ALPHA_RECORDING_MS = 60_000


@dataclass(frozen=True)
class RecordingSafetyCheck:
    id: str
    status: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecordingSafetyGateReport:
    status: str
    score: float
    live_requested: bool
    live_allowed: bool
    confirmation_phrase: str
    duration_ms: int
    generated_at: str
    platform: str
    checks: list[RecordingSafetyCheck]
    recommendation: str
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Recording Safety Gate",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Live requested: `{str(self.live_requested).lower()}`",
            f"- Live allowed: `{str(self.live_allowed).lower()}`",
            f"- Duration: `{self.duration_ms} ms`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            "",
            "## Required confirmation phrase",
            "",
            f"`{self.confirmation_phrase}`",
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "|---|---|---|",
        ]
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | {_md(check.detail)} |")
        lines.extend(["", "## Recommendation", "", self.recommendation, ""])
        return "\n".join(lines)


def evaluate_recording_safety_gate(
    *,
    live_requested: bool,
    confirmation: str | bool | None = None,
    notice_acknowledged: bool = False,
    participants_notified: bool = False,
    duration_ms: int = 3_000,
    publication_hold: bool = True,
) -> RecordingSafetyGateReport:
    """Evaluate whether the alpha may open a real microphone.

    This gate is intentionally conservative. It keeps dry-runs easy while making
    live capture opt-in and auditable. It does not provide legal advice.
    """
    checks: list[RecordingSafetyCheck] = []
    checks.append(
        RecordingSafetyCheck(
            "dry_run_default",
            "pass" if not live_requested else "warn",
            "Dry-run mode does not open a microphone." if not live_requested else "Live capture was requested; stricter consent checks apply.",
        )
    )
    if live_requested:
        confirmed = _confirmation_ok(confirmation)
        checks.append(
            RecordingSafetyCheck(
                "explicit_live_confirmation",
                "pass" if confirmed else "fail",
                "Explicit live capture confirmation was provided."
                if confirmed
                else f"Live capture requires `{LIVE_CONFIRMATION_PHRASE}` or the dedicated confirmation flag.",
            )
        )
        checks.append(
            RecordingSafetyCheck(
                "recording_notice_acknowledged",
                "pass" if notice_acknowledged else "fail",
                "The operator acknowledged the recording/transcription notice."
                if notice_acknowledged
                else "Acknowledge the recording/transcription notice before opening the microphone.",
            )
        )
        checks.append(
            RecordingSafetyCheck(
                "participants_notified",
                "pass" if participants_notified else "fail",
                "The operator confirmed participants were notified."
                if participants_notified
                else "Notify meeting participants before recording real audio.",
            )
        )
    else:
        checks.extend(
            [
                RecordingSafetyCheck("explicit_live_confirmation", "pass", "Not required for dry-run."),
                RecordingSafetyCheck("recording_notice_acknowledged", "pass", "Dry-run only; no microphone is opened."),
                RecordingSafetyCheck("participants_notified", "pass", "Dry-run only; no participants are recorded."),
            ]
        )
    checks.append(
        RecordingSafetyCheck(
            "duration_limit",
            "pass" if 0 < duration_ms <= MAX_ALPHA_RECORDING_MS else "fail",
            f"Duration is within the alpha limit of {MAX_ALPHA_RECORDING_MS} ms."
            if 0 < duration_ms <= MAX_ALPHA_RECORDING_MS
            else f"Limit alpha microphone captures to 1-{MAX_ALPHA_RECORDING_MS} ms.",
            {"max_alpha_recording_ms": MAX_ALPHA_RECORDING_MS},
        )
    )
    checks.append(
        RecordingSafetyCheck(
            "publication_hold",
            "pass" if publication_hold else "warn",
            "Publication gate remains on hold while microphone alpha is validated privately."
            if publication_hold
            else "Publication gate is not on hold; verify public criteria before sharing.",
        )
    )
    checks.append(
        RecordingSafetyCheck("private_core_excluded", "pass", "Private Quality Engine is not included."),
    )
    status = _status(checks)
    live_allowed = bool(live_requested and status in {"pass", "warn"} and not any(c.status == "fail" for c in checks))
    if not live_requested:
        recommendation = "Dry-run is safe. To open the microphone, provide explicit confirmation, acknowledge notice, and confirm participant notification."
    elif live_allowed:
        recommendation = "Live microphone capture is allowed for this controlled alpha run. Keep the repository private and inspect diagnostics after capture."
    else:
        recommendation = "Live microphone capture is blocked. Complete the failed consent/safety checks before retrying."
    return RecordingSafetyGateReport(
        status=status,
        score=_score(checks),
        live_requested=live_requested,
        live_allowed=live_allowed,
        confirmation_phrase=LIVE_CONFIRMATION_PHRASE,
        duration_ms=duration_ms,
        generated_at=utc_now_iso(),
        platform=platform.platform(),
        checks=checks,
        recommendation=recommendation,
        private_core_included=False,
    )


def write_recording_safety_gate_report(report: RecordingSafetyGateReport, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def _confirmation_ok(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip() == LIVE_CONFIRMATION_PHRASE


def _status(checks: list[RecordingSafetyCheck]) -> str:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "pass"


def _score(checks: list[RecordingSafetyCheck]) -> float:
    score = 1.0
    for check in checks:
        if check.status == "warn":
            score -= 0.08
        elif check.status == "fail":
            score -= 0.24
    return round(max(0.0, score), 3)


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
