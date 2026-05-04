from __future__ import annotations
from meeting_agent.desktop.workspace import DesktopAlphaManager, DesktopAlphaReport

def run_desktop_alpha_workflow(*, out_dir, workflow_id="desktop_alpha_demo", capture_provider="simulated", asr_provider="sidecar", sidecar_path=None, sample_transcript_path=None, duration_ms=3000, chunk_ms=250, meeting_id="mtg_desktop_alpha", title="AI Meeting Agent Desktop Alpha") -> DesktopAlphaReport:
    # Community-safe implementation: deterministic simulated workflow. Real capture and heavyweight ASR remain provider extensions.
    return DesktopAlphaManager(out_dir).run_smoke()
