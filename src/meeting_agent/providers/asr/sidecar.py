from __future__ import annotations

from pathlib import Path
from typing import AsyncIterable

from meeting_agent.audio.wav_io import read_wav_info
from meeting_agent.core.schemas import AudioRef, Transcript
from meeting_agent.core.transcript import load_transcript
from meeting_agent.providers.asr.base import ASRCapabilities, ASRProvider, TranscriptDelta


class SidecarTranscriptProvider(ASRProvider):
    """Deterministic file-transcription provider for demos and tests.

    It is not a speech recognition model. It binds a WAV file to a sidecar
    transcript file so the full local audio -> transcript -> minutes workflow can
    be tested without shipping a heavy model or calling a cloud API.
    """

    id = "sidecar_transcript"
    name = "Sidecar Transcript Provider"
    capabilities = ASRCapabilities(
        streaming=False,
        file_transcription=True,
        diarization=False,
        word_timestamps=False,
        languages=("ja", "en", "multi"),
    )

    def __init__(self, sidecar_path: str | Path | None = None) -> None:
        self.sidecar_path = Path(sidecar_path) if sidecar_path else None

    async def transcribe_stream(self, audio_stream: AsyncIterable[bytes]) -> AsyncIterable[TranscriptDelta]:
        raise NotImplementedError("SidecarTranscriptProvider does not support streams")

    def transcribe_file(self, audio_path: str, *, meeting_id: str, title: str = "Untitled Meeting") -> Transcript:
        wav_path = Path(audio_path)
        sidecar = self.sidecar_path or find_sidecar_transcript(wav_path)
        if sidecar is None:
            raise FileNotFoundError(
                "No sidecar transcript found. Expected one of: "
                f"{wav_path.with_suffix('.transcript.json').name}, "
                f"{wav_path.with_suffix('.transcript.txt').name}, "
                f"{wav_path.stem}.txt"
            )
        transcript = load_transcript(sidecar)
        transcript.meeting_id = meeting_id
        transcript.title = title
        transcript.metadata.setdefault("audio", {})
        transcript.metadata["audio"].update(read_wav_info(wav_path).to_dict())
        transcript.metadata["asr_provider"] = self.id
        for segment in transcript.segments:
            segment.source_model = self.id
            segment.audio_ref = AudioRef(
                uri=str(wav_path),
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                provider=self.id,
            )
            segment.metadata.setdefault("sidecar_path", str(sidecar))
        return transcript


def find_sidecar_transcript(audio_path: str | Path) -> Path | None:
    path = Path(audio_path)
    candidates = [
        path.with_suffix(".transcript.json"),
        path.with_suffix(".transcript.txt"),
        path.with_suffix(".json"),
        path.with_suffix(".txt"),
        path.parent / f"{path.stem}.transcript.json",
        path.parent / f"{path.stem}.transcript.txt",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate != path:
            return candidate
    return None
