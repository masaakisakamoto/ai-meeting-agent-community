from __future__ import annotations

from pathlib import Path

from meeting_agent.core.schemas import MinutesDraft, Transcript
from meeting_agent.exporters.markdown import render_minutes_markdown


class ObsidianExportPlugin:
    """Example community plugin: write minutes to an Obsidian vault folder."""

    id = "obsidian_export"
    name = "Obsidian Export Plugin"

    def export(self, transcript: Transcript, minutes: MinutesDraft, vault_dir: str | Path) -> Path:
        vault_dir = Path(vault_dir)
        vault_dir.mkdir(parents=True, exist_ok=True)
        safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in minutes.title).strip()
        path = vault_dir / f"{safe_title or minutes.meeting_id}.md"
        path.write_text(render_minutes_markdown(transcript, minutes), encoding="utf-8")
        return path
