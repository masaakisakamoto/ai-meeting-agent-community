from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class AudioRef:
    uri: str
    start_ms: int
    end_ms: int
    provider: str = "local"


@dataclass
class TranscriptSegment:
    id: str
    text: str
    start_ms: int = 0
    end_ms: int = 0
    speaker_id: str = "spk_unknown"
    speaker_name: str = "Unknown"
    confidence: float = 1.0
    source_model: str = "manual"
    audio_ref: Optional[AudioRef] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compact_quote(self, limit: int = 120) -> str:
        text = " ".join(self.text.split())
        if len(text) <= limit:
            return text
        return text[: limit - 1] + "…"


@dataclass
class Transcript:
    meeting_id: str
    title: str = "Untitled Meeting"
    language: str = "ja"
    segments: List[TranscriptSegment] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def sort_segments(self) -> None:
        self.segments.sort(key=lambda s: (s.start_ms, s.end_ms, s.id))

    def segment_by_id(self) -> Dict[str, TranscriptSegment]:
        return {s.id: s for s in self.segments}


@dataclass
class EvidenceLink:
    segment_id: str
    start_ms: int
    end_ms: int
    speaker_name: str
    quote: str


@dataclass
class Decision:
    id: str
    text: str
    confidence: float
    status: str = "candidate"
    evidence_segment_ids: List[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class ActionItem:
    id: str
    task: str
    owner: str = "未定"
    due_date: str = "未定"
    confidence: float = 0.5
    status: str = "candidate"
    evidence_segment_ids: List[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class OpenQuestion:
    id: str
    text: str
    owner: str = "未定"
    confidence: float = 0.5
    status: str = "candidate"
    evidence_segment_ids: List[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class Risk:
    id: str
    text: str
    severity: str = "medium"
    confidence: float = 0.5
    status: str = "candidate"
    evidence_segment_ids: List[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class TopicBlock:
    title: str
    summary: str
    evidence_segment_ids: List[str] = field(default_factory=list)


@dataclass
class MinutesDraft:
    meeting_id: str
    title: str
    summary: str = ""
    decisions: List[Decision] = field(default_factory=list)
    action_items: List[ActionItem] = field(default_factory=list)
    open_questions: List[OpenQuestion] = field(default_factory=list)
    risks: List[Risk] = field(default_factory=list)
    topics: List[TopicBlock] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    generator: str = "rule-based-community"
    verification_status: str = "unverified"
    quality_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationIssue:
    item_type: str
    item_id: str
    severity: str
    message: str
    evidence_segment_ids: List[str] = field(default_factory=list)


@dataclass
class VerificationReport:
    meeting_id: str
    status: str
    score: float
    issues: List[VerificationIssue] = field(default_factory=list)
    checked_at: str = field(default_factory=utc_now_iso)


def to_dict(obj: Any) -> Dict[str, Any]:
    return asdict(obj)


def _audio_ref_from_dict(data: Optional[Dict[str, Any]]) -> Optional[AudioRef]:
    if data is None:
        return None
    return AudioRef(**data)


def transcript_segment_from_dict(data: Dict[str, Any]) -> TranscriptSegment:
    payload = dict(data)
    payload["audio_ref"] = _audio_ref_from_dict(payload.get("audio_ref"))
    return TranscriptSegment(**payload)


def transcript_from_dict(data: Dict[str, Any]) -> Transcript:
    payload = dict(data)
    payload["segments"] = [transcript_segment_from_dict(s) for s in data.get("segments", [])]
    return Transcript(**payload)


def decision_from_dict(data: Dict[str, Any]) -> Decision:
    return Decision(**data)


def action_item_from_dict(data: Dict[str, Any]) -> ActionItem:
    return ActionItem(**data)


def open_question_from_dict(data: Dict[str, Any]) -> OpenQuestion:
    return OpenQuestion(**data)


def risk_from_dict(data: Dict[str, Any]) -> Risk:
    return Risk(**data)


def topic_block_from_dict(data: Dict[str, Any]) -> TopicBlock:
    return TopicBlock(**data)


def minutes_from_dict(data: Dict[str, Any]) -> MinutesDraft:
    payload = dict(data)
    payload["decisions"] = [decision_from_dict(x) for x in data.get("decisions", [])]
    payload["action_items"] = [action_item_from_dict(x) for x in data.get("action_items", [])]
    payload["open_questions"] = [open_question_from_dict(x) for x in data.get("open_questions", [])]
    payload["risks"] = [risk_from_dict(x) for x in data.get("risks", [])]
    payload["topics"] = [topic_block_from_dict(x) for x in data.get("topics", [])]
    return MinutesDraft(**payload)


def verification_issue_from_dict(data: Dict[str, Any]) -> VerificationIssue:
    return VerificationIssue(**data)


def verification_report_from_dict(data: Dict[str, Any]) -> VerificationReport:
    payload = dict(data)
    payload["issues"] = [verification_issue_from_dict(x) for x in data.get("issues", [])]
    return VerificationReport(**payload)
