from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from meeting_agent.audio import analyze_wav_quality, assess_capture_readiness, capture_session_to_wav
from meeting_agent.providers.audio import AudioCaptureConfig, SimulatedAudioCaptureProvider
from meeting_agent.providers.asr.doctor import run_asr_doctor


class AudioQualityPreflightTests(unittest.TestCase):
    def test_simulated_wav_quality_passes_or_warns_without_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "audio.wav"
            provider = SimulatedAudioCaptureProvider(total_ms=2000)
            config = AudioCaptureConfig(device_id="simulated:microphone", chunk_ms=250)
            capture_session_to_wav(provider, config, session_id="q", wav_path=wav_path)
            report = analyze_wav_quality(wav_path)
            self.assertIn(report.status, {"pass", "warn"})
            self.assertGreater(report.duration_ms, 1500)
            self.assertGreater(report.peak_linear, 0.0)
            self.assertIn("rms_level", report.checks)

    def test_capture_readiness_for_simulated_provider(self) -> None:
        provider = SimulatedAudioCaptureProvider(total_ms=1000)
        config = AudioCaptureConfig(device_id="simulated:microphone", chunk_ms=250)
        report = assess_capture_readiness(provider, config)
        self.assertEqual(report.status, "pass")
        self.assertGreaterEqual(report.score, 0.9)
        self.assertTrue(report.devices)

    def test_asr_doctor_is_json_serializable(self) -> None:
        report = run_asr_doctor("faster-whisper")
        payload = json.loads(report.to_json())
        self.assertEqual(payload["provider"], "faster-whisper")
        self.assertIn(payload["status"], {"pass", "warn", "fail"})
        self.assertTrue(payload["checks"])


if __name__ == "__main__":
    unittest.main()
