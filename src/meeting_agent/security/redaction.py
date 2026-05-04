from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Tuple

from meeting_agent.core.schemas import Transcript

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?81[-\s]?)?0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}(?!\d)")


@dataclass
class RedactionReport:
    replacements: Dict[str, int] = field(default_factory=dict)

    def add(self, kind: str, count: int) -> None:
        self.replacements[kind] = self.replacements.get(kind, 0) + count


def redact_text(text: str) -> tuple[str, RedactionReport]:
    report = RedactionReport()

    def email_sub(match: re.Match) -> str:
        report.add("email", 1)
        return "[REDACTED_EMAIL]"

    def phone_sub(match: re.Match) -> str:
        report.add("phone", 1)
        return "[REDACTED_PHONE]"

    text = EMAIL_RE.sub(email_sub, text)
    text = PHONE_RE.sub(phone_sub, text)
    return text, report


def redact_transcript(transcript: Transcript) -> tuple[Transcript, RedactionReport]:
    aggregate = RedactionReport()
    for segment in transcript.segments:
        redacted, report = redact_text(segment.text)
        segment.text = redacted
        for kind, count in report.replacements.items():
            aggregate.add(kind, count)
    transcript.metadata["redacted"] = True
    transcript.metadata["redaction_report"] = aggregate.replacements
    return transcript, aggregate
