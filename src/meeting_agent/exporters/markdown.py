from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from meeting_agent.core.schemas import MinutesDraft, Transcript, TranscriptSegment
from meeting_agent.core.transcript import format_timestamp


class MarkdownExporter:
    id = "markdown"
    name = "Markdown Exporter"

    def export(self, transcript: Transcript, minutes: MinutesDraft, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_minutes_markdown(transcript, minutes), encoding="utf-8")


def render_minutes_markdown(transcript: Transcript, minutes: MinutesDraft) -> str:
    by_id = transcript.segment_by_id()
    lines: list[str] = []
    lines.append(f"# {minutes.title}")
    lines.append("")
    lines.append(f"- Meeting ID: `{minutes.meeting_id}`")
    lines.append(f"- Generated: `{minutes.created_at}`")
    lines.append(f"- Generator: `{minutes.generator}`")
    lines.append(f"- Verification: `{minutes.verification_status}`")
    if minutes.quality_score is not None:
        lines.append(f"- Quality score: `{minutes.quality_score}`")
    lines.append("")

    lines.append("## 概要")
    lines.append("")
    lines.append(minutes.summary or "（概要なし）")
    lines.append("")

    lines.append("## 決定事項")
    lines.append("")
    if minutes.decisions:
        for item in minutes.decisions:
            lines.append(f"- **{item.text}**  ")
            lines.extend(_evidence_lines(item.evidence_segment_ids, by_id))
    else:
        lines.append("- なし")
    lines.append("")

    lines.append("## ToDo")
    lines.append("")
    if minutes.action_items:
        lines.append("| 担当 | 内容 | 期限 | 信頼度 | 根拠 |")
        lines.append("|---|---|---|---:|---|")
        for item in minutes.action_items:
            evidence = _evidence_inline(item.evidence_segment_ids, by_id)
            lines.append(
                f"| {item.owner} | {item.task} | {item.due_date} | {item.confidence:.2f} | {evidence} |"
            )
    else:
        lines.append("- なし")
    lines.append("")

    lines.append("## 未解決論点")
    lines.append("")
    if minutes.open_questions:
        for item in minutes.open_questions:
            lines.append(f"- {item.text}  ")
            lines.extend(_evidence_lines(item.evidence_segment_ids, by_id))
    else:
        lines.append("- なし")
    lines.append("")

    lines.append("## リスク・懸念")
    lines.append("")
    if minutes.risks:
        for item in minutes.risks:
            lines.append(f"- [{item.severity}] {item.text}  ")
            lines.extend(_evidence_lines(item.evidence_segment_ids, by_id))
    else:
        lines.append("- なし")
    lines.append("")

    lines.append("## トピック")
    lines.append("")
    if minutes.topics:
        for topic in minutes.topics:
            lines.append(f"### {topic.title}")
            lines.append(topic.summary)
            lines.extend(_evidence_lines(topic.evidence_segment_ids, by_id))
            lines.append("")
    else:
        lines.append("- なし")
    return "\n".join(lines).rstrip() + "\n"


def _evidence_lines(evidence_ids: Sequence[str], by_id: dict[str, TranscriptSegment]) -> list[str]:
    lines = []
    for segment_id in evidence_ids:
        seg = by_id.get(segment_id)
        if seg:
            lines.append(
                f"  - 根拠: `{format_timestamp(seg.start_ms)}-{format_timestamp(seg.end_ms)}` "
                f"{seg.speaker_name}: “{seg.compact_quote(90)}”"
            )
        else:
            lines.append(f"  - 根拠: `{segment_id}` not found")
    return lines


def _evidence_inline(evidence_ids: Sequence[str], by_id: dict[str, TranscriptSegment]) -> str:
    parts = []
    for segment_id in evidence_ids:
        seg = by_id.get(segment_id)
        if seg:
            parts.append(f"{format_timestamp(seg.start_ms)} {seg.speaker_name}: {seg.compact_quote(40)}")
        else:
            parts.append(f"{segment_id} not found")
    return "<br>".join(parts)
