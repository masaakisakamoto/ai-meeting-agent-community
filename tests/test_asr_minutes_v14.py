from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from meeting_agent.audio.wav_io import write_wav_from_chunks
from meeting_agent.cli import main
from meeting_agent.desktop.bridge import BridgeConfig, handle_bridge_request
from meeting_agent.providers.audio import AudioCaptureConfig, SimulatedAudioCaptureProvider
from meeting_agent.workflows.asr_minutes import run_asr_to_minutes_workflow


class ASRMinutesV14Tests(unittest.TestCase):
    def _make_audio(self, root: Path) -> tuple[Path, Path]:
        provider = SimulatedAudioCaptureProvider(total_ms=1000)
        config = AudioCaptureConfig(device_id="simulated:microphone", sample_rate_hz=16000, channels=1, chunk_ms=250)
        audio = root / "audio.wav"
        write_wav_from_chunks(list(provider.capture(config, session_id="asr_minutes")), audio)
        sidecar = root / "audio.transcript.txt"
        sidecar.write_text(
            "[00:00:00 - 00:00:01] 佐藤: v1.4ではASRから議事録までつなぐことで決定します。\n"
            "[00:00:01 - 00:00:02] 田中: 山田さん、金曜までにASR議事録レポートの確認をお願いします。\n",
            encoding="utf-8",
        )
        return audio, sidecar

    def test_asr_to_minutes_generates_evidence_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio, sidecar = self._make_audio(root)
            out = root / "asr_minutes"
            report = run_asr_to_minutes_workflow(audio_path=audio, out_dir=out, provider="sidecar", sidecar_path=sidecar, reference_path=sidecar)
            self.assertIn(report.status, {"pass", "warn"})
            self.assertFalse(report.private_core_included)
            self.assertTrue((out / "minutes.html").exists())
            self.assertTrue((out / "quality_gate.json").exists())
            self.assertTrue((out / "asr_validation" / "metrics.json").exists())
            self.assertEqual(report.metrics["cer"], 0.0)
            self.assertGreaterEqual(report.summary["decisions"], 1)

    def test_cli_asr_to_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio, sidecar = self._make_audio(root)
            out = root / "cli_asr_minutes"
            code = main(["asr-to-minutes", "--audio-path", str(audio), "--provider", "sidecar", "--sidecar", str(sidecar), "--reference", str(sidecar), "--out-dir", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue((out / "asr_minutes_report.json").exists())
            self.assertTrue((out / "desktop_lite" / "index.html").exists())

    def test_bridge_asr_to_minutes_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_audio(root)
            status, payload = handle_bridge_request("POST", "/api/workflows/asr-to-minutes", {"run_id": "unit", "provider": "sidecar"}, config=BridgeConfig(workspace=root))
            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["workflow"]["id"], "asr-to-minutes")
            self.assertFalse(payload["private_core_included"])
            self.assertIn("asr_minutes", payload)


if __name__ == "__main__":
    unittest.main()
