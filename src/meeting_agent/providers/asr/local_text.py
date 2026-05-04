from __future__ import annotations

from typing import AsyncIterable

from meeting_agent.core.transcript import load_transcript, parse_plain_text_transcript
from meeting_agent.core.schemas import Transcript
from meeting_agent.providers.asr.base import ASRCapabilities, ASRProvider, TranscriptDelta


class LocalTextTranscriptProvider(ASRProvider):
    """Provider used for testing and transcript-only workflows."""

    id = "local_text"
    name = "Local Text Transcript Provider"
    capabilities = ASRCapabilities(streaming=False, file_transcription=True, diarization=False)

    async def transcribe_stream(self, audio_stream: AsyncIterable[bytes]) -> AsyncIterable[TranscriptDelta]:
        raise NotImplementedError("LocalTextTranscriptProvider does not support audio streams")

    def transcribe_file(self, audio_path: str, *, meeting_id: str, title: str = "Untitled Meeting") -> Transcript:
        transcript = load_transcript(audio_path)
        transcript.meeting_id = meeting_id
        transcript.title = title
        return transcript
