import unittest

from meeting_agent.core.transcript import parse_plain_text_transcript
from meeting_agent.providers.audio import AudioCaptureConfig, SimulatedAudioCaptureProvider
from meeting_agent.streaming.replay import TranscriptReplaySettings, iter_transcript_replay_events, transcript_replay_payload


class ReplayAndAudioTest(unittest.TestCase):
    def test_transcript_replay_events_are_deterministic_and_complete(self) -> None:
        transcript = parse_plain_text_transcript(
            "[00:00:01] 佐藤: v0.3のUIを確認します。\n[00:00:04] 鈴木: 金曜までに録音プロバイダを調査します。",
            meeting_id="mtg_replay",
            title="Replay test",
        )
        settings = TranscriptReplaySettings(chars_per_delta=8, min_delta_ms=50, speed=2.0)
        events = list(iter_transcript_replay_events(transcript, settings))

        self.assertEqual(events[0].type, "segment_start")
        self.assertEqual(events[-1].type, "meeting_end")
        self.assertEqual({event.segment_id for event in events if event.segment_id}, {"seg_0001", "seg_0002"})
        self.assertTrue(all(events[i].sequence < events[i + 1].sequence for i in range(len(events) - 1)))
        self.assertTrue(all(events[i].offset_ms <= events[i + 1].offset_ms for i in range(len(events) - 1)))

    def test_transcript_replay_payload_contains_meeting_metadata(self) -> None:
        transcript = parse_plain_text_transcript("[00:00:01] 佐藤: 決定します。", meeting_id="mtg_payload")
        payload = transcript_replay_payload(transcript)
        self.assertEqual(payload["meeting"]["meeting_id"], "mtg_payload")
        self.assertEqual(payload["meeting"]["segment_count"], 1)
        self.assertEqual(payload["events"][-1]["type"], "meeting_end")

    def test_simulated_audio_provider_generates_chunks_without_device_access(self) -> None:
        provider = SimulatedAudioCaptureProvider(total_ms=1000)
        devices = provider.list_devices()
        self.assertEqual(devices[0].id, "simulated:microphone")
        chunks = list(provider.capture(AudioCaptureConfig(device_id=devices[0].id, chunk_ms=250), session_id="s1"))
        self.assertEqual(len(chunks), 4)
        self.assertEqual(chunks[0].sequence, 1)
        self.assertEqual(chunks[-1].end_ms, 1000)
        self.assertTrue(chunks[0].pcm_s16le)
        self.assertTrue(chunks[0].to_public_dict()["pcm_s16le"].endswith("bytes>"))


if __name__ == "__main__":
    unittest.main()
