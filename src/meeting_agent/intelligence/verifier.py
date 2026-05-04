from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from meeting_agent.core.schemas import (
    ActionItem,
    Decision,
    MinutesDraft,
    OpenQuestion,
    Risk,
    Transcript,
    VerificationIssue,
    VerificationReport,
)


@dataclass
class MinutesVerifier:
    min_overlap: float = 0.12

    def verify(self, transcript: Transcript, minutes: MinutesDraft) -> VerificationReport:
        by_id = transcript.segment_by_id()
        issues: list[VerificationIssue] = []

        for item in minutes.decisions:
            issues.extend(self._check_item("decision", item.id, item.text, item.evidence_segment_ids, by_id))
        for item in minutes.action_items:
            text = f"{item.owner} {item.task} {item.due_date}"
            issues.extend(self._check_item("action_item", item.id, text, item.evidence_segment_ids, by_id))
        for item in minutes.open_questions:
            issues.extend(self._check_item("open_question", item.id, item.text, item.evidence_segment_ids, by_id))
        for item in minutes.risks:
            issues.extend(self._check_item("risk", item.id, item.text, item.evidence_segment_ids, by_id))

        penalty = 0.0
        for issue in issues:
            penalty += {"low": 0.04, "medium": 0.1, "high": 0.2}.get(issue.severity, 0.1)
        score = max(0.0, round(1.0 - penalty, 3))
        status = "pass" if score >= 0.8 and not any(i.severity == "high" for i in issues) else "needs_review"
        minutes.verification_status = status
        minutes.quality_score = score
        return VerificationReport(meeting_id=transcript.meeting_id, status=status, score=score, issues=issues)

    def _check_item(self, item_type: str, item_id: str, text: str, evidence_ids: Sequence[str], by_id: dict) -> list[VerificationIssue]:
        issues: list[VerificationIssue] = []
        if not evidence_ids:
            return [
                VerificationIssue(
                    item_type=item_type,
                    item_id=item_id,
                    severity="high",
                    message="No evidence segment linked.",
                )
            ]
        evidence_texts = []
        missing = []
        for evidence_id in evidence_ids:
            if evidence_id not in by_id:
                missing.append(evidence_id)
            else:
                evidence_texts.append(by_id[evidence_id].text)
        if missing:
            issues.append(
                VerificationIssue(
                    item_type=item_type,
                    item_id=item_id,
                    severity="high",
                    message=f"Evidence segment IDs not found: {', '.join(missing)}",
                    evidence_segment_ids=list(evidence_ids),
                )
            )
        if evidence_texts:
            overlap = grounding_overlap(text, " ".join(evidence_texts))
            if overlap < self.min_overlap:
                issues.append(
                    VerificationIssue(
                        item_type=item_type,
                        item_id=item_id,
                        severity="medium",
                        message=f"Weak lexical grounding overlap: {overlap:.3f}",
                        evidence_segment_ids=list(evidence_ids),
                    )
                )
        return issues


def grounding_overlap(claim: str, evidence: str) -> float:
    claim_tokens = set(_tokens(claim))
    evidence_tokens = set(_tokens(evidence))
    if not claim_tokens:
        return 1.0
    return len(claim_tokens & evidence_tokens) / len(claim_tokens)


def _tokens(text: str) -> list[str]:
    text = re.sub(r"\s+", "", text.lower())
    # Mix Japanese character bigrams and alphanumeric tokens.
    alpha = re.findall(r"[a-z0-9_\-]{2,}", text)
    chars = [c for c in text if not re.match(r"\s", c)]
    bigrams = ["".join(chars[i : i + 2]) for i in range(max(0, len(chars) - 1))]
    return alpha + bigrams
