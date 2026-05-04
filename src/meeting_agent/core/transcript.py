from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List, Optional

from .schemas import Transcript, TranscriptSegment, to_dict, transcript_from_dict

TIMESTAMP_RE = re.compile(
    r"^\s*\[?(?P<start>\d{1,2}:\d{2}(?::\d{2})?(?:\.\d{1,3})?)\]?"
    r"(?:\s*(?:-|–|—|to)\s*\[?(?P<end>\d{1,2}:\d{2}(?::\d{2})?(?:\.\d{1,3})?)\]?)?"
    r"\s*(?P<rest>.*)$"
)
SPEAKER_RE = re.compile(r"^\s*(?P<speaker>[^:：]{1,40})\s*[:：]\s*(?P<text>.+)$")


def parse_timestamp_to_ms(value: str) -> int:
    value = value.strip().strip("[]")
    if not value:
        return 0
    main, _, frac = value.partition(".")
    parts = [int(p) for p in main.split(":")]
    if len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError(f"Invalid timestamp: {value}")
    ms = (hours * 3600 + minutes * 60 + seconds) * 1000
    if frac:
        ms += int((frac + "000")[:3])
    return ms


def format_timestamp(ms: int) -> str:
    if ms < 0:
        ms = 0
    seconds, milli = divmod(ms, 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    if milli:
        return f"{hours:02d}:{minute:02d}:{sec:02d}.{milli:03d}"
    return f"{hours:02d}:{minute:02d}:{sec:02d}"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def split_sentences(text: str) -> List[str]:
    text = normalize_text(text)
    if not text:
        return []
    chunks = re.split(r"(?<=[。！？!?])\s*", text)
    return [c.strip() for c in chunks if c.strip()]


def _speaker_id(speaker_name: str) -> str:
    cleaned = re.sub(r"\W+", "_", speaker_name.lower()).strip("_")
    return f"spk_{cleaned or 'unknown'}"


def parse_plain_text_transcript(
    text: str,
    meeting_id: str = "mtg_local",
    title: str = "Untitled Meeting",
    language: str = "ja",
    default_segment_ms: int = 15_000,
) -> Transcript:
    segments: List[TranscriptSegment] = []
    cursor_ms = 0

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for idx, line in enumerate(lines, start=1):
        start_ms: Optional[int] = None
        end_ms: Optional[int] = None
        rest = line

        ts_match = TIMESTAMP_RE.match(line)
        if ts_match and ts_match.group("start"):
            candidate_rest = ts_match.group("rest") or ""
            # Avoid treating "佐藤: text" as timestamp just because it starts with numbers in rare cases.
            if candidate_rest:
                start_ms = parse_timestamp_to_ms(ts_match.group("start"))
                end_ms = parse_timestamp_to_ms(ts_match.group("end")) if ts_match.group("end") else None
                rest = candidate_rest.strip()

        speaker_name = "Unknown"
        text_value = rest
        sp_match = SPEAKER_RE.match(rest)
        if sp_match:
            speaker_name = sp_match.group("speaker").strip()
            text_value = sp_match.group("text").strip()

        if start_ms is None:
            start_ms = cursor_ms
        if end_ms is None:
            end_ms = max(start_ms + default_segment_ms, cursor_ms + default_segment_ms)

        cursor_ms = end_ms
        segments.append(
            TranscriptSegment(
                id=f"seg_{idx:04d}",
                speaker_name=speaker_name,
                speaker_id=_speaker_id(speaker_name),
                start_ms=start_ms,
                end_ms=end_ms,
                text=normalize_text(text_value),
                confidence=1.0,
                source_model="plain-text-parser",
            )
        )

    transcript = Transcript(meeting_id=meeting_id, title=title, language=language, segments=segments)
    transcript.sort_segments()
    return transcript


def segments_to_text(segments: Iterable[TranscriptSegment], include_timestamps: bool = True) -> str:
    lines = []
    for s in segments:
        prefix = f"[{format_timestamp(s.start_ms)}] " if include_timestamps else ""
        lines.append(f"{prefix}{s.speaker_name}: {s.text}")
    return "\n".join(lines)


def load_transcript(path: str | Path) -> Transcript:
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
        return transcript_from_dict(data)
    return parse_plain_text_transcript(raw, meeting_id=path.stem, title=path.stem)


def save_transcript(transcript: Transcript, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_dict(transcript), ensure_ascii=False, indent=2), encoding="utf-8")
