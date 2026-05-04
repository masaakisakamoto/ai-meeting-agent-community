from __future__ import annotations

import html
from pathlib import Path
from typing import Sequence

from meeting_agent.core.schemas import MinutesDraft, Transcript, TranscriptSegment
from meeting_agent.core.transcript import format_timestamp


class HTMLExporter:
    id = "html"
    name = "Evidence-linked HTML Exporter"

    def export(self, transcript: Transcript, minutes: MinutesDraft, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_minutes_html(transcript, minutes), encoding="utf-8")


def render_minutes_html(transcript: Transcript, minutes: MinutesDraft) -> str:
    by_id = transcript.segment_by_id()
    title = _e(minutes.title)
    rows = []
    for item in minutes.action_items:
        rows.append(
            "<tr>"
            f"<td>{_e(item.owner)}</td>"
            f"<td>{_e(item.task)}</td>"
            f"<td>{_e(item.due_date)}</td>"
            f"<td>{item.confidence:.2f}</td>"
            f"<td>{_evidence_links(item.evidence_segment_ids, by_id)}</td>"
            "</tr>"
        )
    actions = "\n".join(rows) if rows else '<tr><td colspan="5">なし</td></tr>'

    decisions = _list_with_evidence([(d.text, d.evidence_segment_ids) for d in minutes.decisions], by_id)
    questions = _list_with_evidence([(q.text, q.evidence_segment_ids) for q in minutes.open_questions], by_id)
    risks = _list_with_evidence([(f"[{r.severity}] {r.text}", r.evidence_segment_ids) for r in minutes.risks], by_id)
    transcript_html = "\n".join(_transcript_segment_html(seg) for seg in transcript.segments)

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.65; max-width: 1080px; margin: 0 auto; padding: 32px; color: #172033; }}
    header {{ border-bottom: 1px solid #e5e7eb; margin-bottom: 24px; }}
    .meta {{ color: #64748b; font-size: 0.92rem; }}
    section {{ margin: 32px 0; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; vertical-align: top; }}
    .evidence {{ color: #334155; font-size: 0.92rem; }}
    .segment {{ padding: 10px 12px; border-left: 3px solid #cbd5e1; margin: 8px 0; background: #f8fafc; }}
    .segment:target {{ outline: 3px solid #93c5fd; background: #eff6ff; }}
    .time {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #475569; }}
    a {{ color: #2563eb; text-decoration: none; }}
  </style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <p class="meta">Meeting ID: {_e(minutes.meeting_id)} / Generator: {_e(minutes.generator)} / Verification: {_e(minutes.verification_status)} / Quality: {_e(str(minutes.quality_score))}</p>
</header>
<section>
  <h2>概要</h2>
  <p>{_e(minutes.summary or '（概要なし）')}</p>
</section>
<section>
  <h2>決定事項</h2>
  {decisions}
</section>
<section>
  <h2>ToDo</h2>
  <table><thead><tr><th>担当</th><th>内容</th><th>期限</th><th>信頼度</th><th>根拠</th></tr></thead><tbody>{actions}</tbody></table>
</section>
<section>
  <h2>未解決論点</h2>
  {questions}
</section>
<section>
  <h2>リスク・懸念</h2>
  {risks}
</section>
<section>
  <h2>発言ログ</h2>
  {transcript_html}
</section>
</body>
</html>
"""


def _list_with_evidence(items: Sequence[tuple[str, Sequence[str]]], by_id: dict[str, TranscriptSegment]) -> str:
    if not items:
        return "<p>なし</p>"
    out = ["<ul>"]
    for text, evidence_ids in items:
        out.append(f"<li><strong>{_e(text)}</strong><div class='evidence'>{_evidence_links(evidence_ids, by_id)}</div></li>")
    out.append("</ul>")
    return "\n".join(out)


def _evidence_links(evidence_ids: Sequence[str], by_id: dict[str, TranscriptSegment]) -> str:
    parts: list[str] = []
    for segment_id in evidence_ids:
        seg = by_id.get(segment_id)
        if seg:
            label = f"{format_timestamp(seg.start_ms)} {seg.speaker_name}: {seg.compact_quote(42)}"
            parts.append(f"<a href='#{_e(segment_id)}'>{_e(label)}</a>")
        else:
            parts.append(_e(f"{segment_id} not found"))
    return "<br />".join(parts) if parts else "根拠なし"


def _transcript_segment_html(seg: TranscriptSegment) -> str:
    return (
        f"<div class='segment' id='{_e(seg.id)}'>"
        f"<span class='time'>{_e(format_timestamp(seg.start_ms))}-{_e(format_timestamp(seg.end_ms))}</span> "
        f"<strong>{_e(seg.speaker_name)}</strong>: {_e(seg.text)}"
        "</div>"
    )


def _e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)
