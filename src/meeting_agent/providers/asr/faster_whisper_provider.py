from __future__ import annotations

from typing import AsyncIterable

from meeting_agent.core.schemas import Transcript, TranscriptSegment
from meeting_agent.providers.asr.base import ASRCapabilities, ASRProvider, TranscriptDelta


class FasterWhisperProvider(ASRProvider):
    """Optional ASR provider. Install with `pip install .[asr]`.

    This adapter is intentionally thin. Production systems should add VAD,
    chunking, retry, model routing, and word-level timestamp normalization.
    """

    id = "faster_whisper"
    name = "faster-whisper"
    capabilities = ASRCapabilities(
        streaming=False,
        file_transcription=True,
        diarization=False,
        word_timestamps=True,
        languages=("ja", "en", "multi"),
    )

    def __init__(self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError(
                    "faster-whisper is not installed. Run `pip install .[asr]` or install faster-whisper."
                ) from exc
            self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        return self._model

    async def transcribe_stream(self, audio_stream: AsyncIterable[bytes]) -> AsyncIterable[TranscriptDelta]:
        raise NotImplementedError("faster-whisper streaming requires a chunking/VAD layer")

    def transcribe_file(self, audio_path: str, *, meeting_id: str, title: str = "Untitled Meeting") -> Transcript:
        model = self._load_model()
        segments, info = model.transcribe(audio_path, language="ja", vad_filter=True)
        out = []
        for idx, seg in enumerate(segments, start=1):
            out.append(
                TranscriptSegment(
                    id=f"seg_{idx:04d}",
                    text=seg.text.strip(),
                    start_ms=int(seg.start * 1000),
                    end_ms=int(seg.end * 1000),
                    speaker_name="Unknown",
                    speaker_id="spk_unknown",
                    confidence=1.0,
                    source_model=f"faster-whisper:{self.model_size}",
                    metadata={"language": getattr(info, "language", "unknown")},
                )
            )
        return Transcript(meeting_id=meeting_id, title=title, language="ja", segments=out)
