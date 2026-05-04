import tempfile
import unittest
from pathlib import Path

from meeting_agent.audio import capture_session_to_wav, read_wav_info
from meeting_agent.core.transcript import save_transcript, parse_plain_text_transcript
from meeting_agent.providers.asr.sidecar import SidecarTranscriptProvider, find_sidecar_transcript
from meeting_agent.providers.audio import AudioCaptureConfig, SimulatedAudioCaptureProvider, WavFileAudioProvider


class AudioWorkflowTest(unittest.TestCase):
    def test_capture_session_to_wav_writes_manifest_and_valid_wav(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            provider = SimulatedAudioCaptureProvider(total_ms=1000)
            config = AudioCaptureConfig(device_id="simulated:microphone", chunk_ms=250)
            manifest = capture_session_to_wav(
                provider,
                config,
                session_id="session_test",
                wav_path=out / "audio.wav",
                manifest_path=out / "audio_session.json",
            )
            self.assertTrue((out / "audio.wav").exists())
            self.assertTrue((out / "audio_session.json").exists())
            self.assertEqual(manifest.chunk_count, 4)
            self.assertEqual(manifest.duration_ms, 1000)
            wav_info = read_wav_info(out / "audio.wav")
            self.assertEqual(wav_info.sample_rate_hz, 16000)
            self.assertEqual(wav_info.channels, 1)
            self.assertEqual(wav_info.duration_ms, 1000)

    def test_wav_file_audio_provider_replays_existing_wav(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            provider = SimulatedAudioCaptureProvider(total_ms=500)
            config = AudioCaptureConfig(device_id="simulated:microphone", chunk_ms=250)
            capture_session_to_wav(provider, config, session_id="source", wav_path=out / "audio.wav")
            file_provider = WavFileAudioProvider(out / "audio.wav")
            devices = file_provider.list_devices()
            self.assertEqual(devices[0].kind, "file")
            chunks = list(file_provider.capture(config, session_id="replay"))
            self.assertEqual(len(chunks), 2)
            self.assertEqual(chunks[-1].end_ms, 500)
            self.assertTrue(chunks[0].pcm_s16le)

    def test_sidecar_transcript_provider_attaches_audio_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            audio_provider = SimulatedAudioCaptureProvider(total_ms=1500)
            config = AudioCaptureConfig(device_id="simulated:microphone", chunk_ms=250)
            capture_session_to_wav(audio_provider, config, session_id="audio", wav_path=out / "meeting.wav")
            transcript = parse_plain_text_transcript("[00:00:00] 佐藤: v0.5を開始します。", meeting_id="sidecar")
            save_transcript(transcript, out / "meeting.transcript.json")
            self.assertEqual(find_sidecar_transcript(out / "meeting.wav"), out / "meeting.transcript.json")
            result = SidecarTranscriptProvider().transcribe_file(
                str(out / "meeting.wav"),
                meeting_id="mtg_from_audio",
                title="Audio workflow",
            )
            self.assertEqual(result.meeting_id, "mtg_from_audio")
            self.assertEqual(result.metadata["asr_provider"], "sidecar_transcript")
            self.assertEqual(result.segments[0].audio_ref.uri, str(out / "meeting.wav"))
            self.assertEqual(result.segments[0].source_model, "sidecar_transcript")


if __name__ == "__main__":
    unittest.main()
