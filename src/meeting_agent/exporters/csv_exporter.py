from __future__ import annotations

import csv
from pathlib import Path

from meeting_agent.core.schemas import MinutesDraft, Transcript


class ActionItemCSVExporter:
    id = "csv.action_items"
    name = "Action Item CSV Exporter"

    def export(self, transcript: Transcript, minutes: MinutesDraft, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        by_id = transcript.segment_by_id()
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["id", "owner", "task", "due_date", "confidence", "status", "evidence"],
            )
            writer.writeheader()
            for item in minutes.action_items:
                evidence = []
                for segment_id in item.evidence_segment_ids:
                    seg = by_id.get(segment_id)
                    if seg:
                        evidence.append(f"{seg.start_ms}-{seg.end_ms} {seg.speaker_name}: {seg.compact_quote(80)}")
                    else:
                        evidence.append(f"{segment_id} not found")
                writer.writerow(
                    {
                        "id": item.id,
                        "owner": item.owner,
                        "task": item.task,
                        "due_date": item.due_date,
                        "confidence": f"{item.confidence:.2f}",
                        "status": item.status,
                        "evidence": " | ".join(evidence),
                    }
                )
