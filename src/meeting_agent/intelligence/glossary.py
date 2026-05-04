from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from meeting_agent.core.schemas import Transcript, TranscriptSegment, to_dict, transcript_from_dict


@dataclass(frozen=True)
class GlossaryEntry:
    canonical: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    type: str = "term"
    case_sensitive: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlossaryEntry":
        aliases = data.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        return cls(
            canonical=str(data["canonical"]),
            aliases=tuple(str(a) for a in aliases),
            type=str(data.get("type", "term")),
            case_sensitive=bool(data.get("case_sensitive", False)),
        )


@dataclass
class TermCorrection:
    segment_id: str
    alias: str
    canonical: str
    count: int
    type: str = "term"


@dataclass
class GlossaryReport:
    corrected_segments: int = 0
    total_replacements: int = 0
    corrections: list[TermCorrection] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "corrected_segments": self.corrected_segments,
            "total_replacements": self.total_replacements,
            "corrections": [c.__dict__ for c in self.corrections],
        }


def load_glossary(path: str | Path) -> list[GlossaryEntry]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = data.get("terms", data if isinstance(data, list) else [])
    return [GlossaryEntry.from_dict(item) for item in entries]


def apply_glossary_to_text(text: str, entries: Iterable[GlossaryEntry]) -> tuple[str, list[tuple[str, str, int, str]]]:
    """Apply term canonicalization while keeping a transparent correction log.

    The Community implementation is deliberately simple and deterministic. The
    private Quality Engine can replace this with phonetic correction, ASR lattice
    rescoring, meeting-context-aware correction, and confidence scoring.
    """
    out = text
    changes: list[tuple[str, str, int, str]] = []
    for entry in entries:
        aliases = [a for a in entry.aliases if a and a != entry.canonical]
        # Longest aliases first prevents partial replacements from hiding longer ones.
        for alias in sorted(aliases, key=len, reverse=True):
            flags = 0 if entry.case_sensitive else re.IGNORECASE
            # For ASCII-like terms, avoid replacing inside a larger token.
            if re.fullmatch(r"[A-Za-z0-9_.\-\s]+", alias):
                pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(alias)}(?![A-Za-z0-9_])", flags)
            else:
                pattern = re.compile(re.escape(alias), flags)
            out, count = pattern.subn(entry.canonical, out)
            if count:
                changes.append((alias, entry.canonical, count, entry.type))
    return out, changes


def apply_glossary(transcript: Transcript, entries: Iterable[GlossaryEntry]) -> tuple[Transcript, GlossaryReport]:
    entries = list(entries)
    corrected = transcript_from_dict(to_dict(transcript))
    report = GlossaryReport()
    for segment in corrected.segments:
        new_text, changes = apply_glossary_to_text(segment.text, entries)
        if new_text != segment.text:
            segment.text = new_text
            report.corrected_segments += 1
            segment.metadata = dict(segment.metadata)
            segment.metadata.setdefault("term_corrections", [])
            for alias, canonical, count, typ in changes:
                report.total_replacements += count
                correction = TermCorrection(
                    segment_id=segment.id,
                    alias=alias,
                    canonical=canonical,
                    count=count,
                    type=typ,
                )
                report.corrections.append(correction)
                segment.metadata["term_corrections"].append(correction.__dict__)
    return corrected, report
