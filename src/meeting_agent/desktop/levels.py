"""Desktop bridge wrappers for dependency-free audio level reports."""
from __future__ import annotations
from pathlib import Path
from meeting_agent.audio import analyze_audio_levels, write_audio_level_report
from meeting_agent.audio.levels import AudioLevelReport

def wav_level_report(audio_path: str | Path, *, frame_ms: int = 100) -> AudioLevelReport:
    return analyze_audio_levels(audio_path, window_ms=frame_ms)

def write_wav_level_report(audio_path: str | Path, out_json: str | Path, *, frame_ms: int = 100, out_md: str | Path | None = None) -> AudioLevelReport:
    report = wav_level_report(audio_path, frame_ms=frame_ms)
    write_audio_level_report(report, out_json=out_json, out_md=out_md)
    return report
