from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from meeting_agent.audio.wav_io import WavInfo, chunk_timeline, write_wav_from_chunks
from meeting_agent.core.schemas import utc_now_iso
from meeting_agent.providers.audio.base import AudioCaptureConfig, AudioCaptureProvider, AudioChunk


@dataclass
class AudioSessionManifest:
    session_id: str
    provider_id: str
    provider_name: str
    config: dict
    wav: dict
    chunk_count: int
    duration_ms: int
    started_at: str
    ended_at: str
    chunks: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def capture_session_to_wav(
    provider: AudioCaptureProvider,
    config: AudioCaptureConfig,
    *,
    session_id: str,
    wav_path: str | Path,
    manifest_path: str | Path | None = None,
    include_chunk_timeline: bool = True,
) -> AudioSessionManifest:
    """Capture one provider session and persist it as WAV + manifest.

    Real microphone/system capture will be implemented as optional providers.
    This workflow is provider-neutral, so the same path works for simulated,
    browser, desktop, file, WASAPI, CoreAudio, PipeWire, or bot-based capture.
    """

    started_at = utc_now_iso()
    chunks = list(provider.capture(config, session_id=session_id))
    wav_info = write_wav_from_chunks(chunks, wav_path)
    ended_at = utc_now_iso()
    manifest = build_audio_session_manifest(
        session_id=session_id,
        provider_id=provider.id,
        provider_name=provider.name,
        config=config,
        wav_info=wav_info,
        chunks=chunks,
        started_at=started_at,
        ended_at=ended_at,
        include_chunk_timeline=include_chunk_timeline,
    )
    if manifest_path:
        out = Path(manifest_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(manifest.to_json() + "\n", encoding="utf-8")
    return manifest


def build_audio_session_manifest(
    *,
    session_id: str,
    provider_id: str,
    provider_name: str,
    config: AudioCaptureConfig,
    wav_info: WavInfo,
    chunks: Iterable[AudioChunk],
    started_at: str,
    ended_at: str,
    include_chunk_timeline: bool = True,
) -> AudioSessionManifest:
    chunk_list = list(chunks)
    return AudioSessionManifest(
        session_id=session_id,
        provider_id=provider_id,
        provider_name=provider_name,
        config=config.to_dict(),
        wav=wav_info.to_dict(),
        chunk_count=len(chunk_list),
        duration_ms=wav_info.duration_ms,
        started_at=started_at,
        ended_at=ended_at,
        chunks=chunk_timeline(chunk_list) if include_chunk_timeline else [],
        metadata={
            "pipeline": "audio-capture-to-wav",
            "oss_safe": True,
            "private_quality_engine_required": False,
        },
    )
