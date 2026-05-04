from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from meeting_agent.audio.wav_io import write_wav_from_chunks
from meeting_agent.desktop.bridge import BridgeConfig, handle_bridge_request
from meeting_agent.providers.audio import AudioCaptureConfig, SimulatedAudioCaptureProvider
from meeting_agent.workflows.microphone_minutes import evaluate_post_capture_gate, run_microphone_to_minutes_workflow


class MicrophoneMinutesV11Test(unittest.TestCase):
    def _make_audio_dir(self, root: Path) -> tuple[Path, Path]:
        provider = SimulatedAudioCaptureProvider(total_ms=1000)
        config = AudioCaptureConfig(device_id="simulated:microphone", sample_rate_hz=16000, channels=1, chunk_ms=250)
        chunks = list(provider.capture(config, session_id="mic_post_capture"))
        audio = root / "audio.wav"
        write_wav_from_chunks(chunks, audio)
        sidecar = root / "audio.transcript.txt"
        sidecar.write_text(
            "[00:00:00 - 00:00:01] 佐藤: v1.1では録音後の議事録生成を追加することで決定します。\n"
            "[00:00:01 - 00:00:02] 田中: 鈴木さん、明日までにポストキャプチャー導線を確認お願いします。\n",
            encoding="utf-8",
        )
        return audio, sidecar

    def test_post_capture_gate_accepts_audio_and_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio, sidecar = self._make_audio_dir(root)
            report = evaluate_post_capture_gate(root, audio_path=audio, provider="sidecar", sidecar_path=sidecar)
            self.assertIn(report.status, {"pass", "warn"})
            self.assertFalse(report.private_core_included)
            ids = {check.id for check in report.checks}
            self.assertIn("audio_wav", ids)
            self.assertIn("sidecar_transcript", ids)

    def test_microphone_to_minutes_generates_evidence_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio, sidecar = self._make_audio_dir(root)
            out = root / "minutes_out"
            report = run_microphone_to_minutes_workflow(
                mic_dir=root,
                audio_path=audio,
                sidecar_path=sidecar,
                out_dir=out,
                provider="sidecar",
                meeting_id="mtg_v11_test",
                title="v1.1 Post Capture Test",
            )
            self.assertIn(report.status, {"pass", "warn"})
            self.assertFalse(report.private_core_included)
            self.assertTrue((out / "minutes.html").exists())
            self.assertTrue((out / "microphone_minutes_report.md").exists())
            self.assertGreaterEqual(report.summary["transcript_segments"], 1)

    def test_bridge_microphone_to_minutes_route_uses_workspace_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_audio_dir(root)
            config = BridgeConfig(workspace=root)
            status, gate = handle_bridge_request("GET", "/api/post-capture/gate", {}, config=config)
            self.assertEqual(status, 200)
            self.assertIn(gate["status"], {"ok", "fail"})
            status, payload = handle_bridge_request("POST", "/api/workflows/microphone-to-minutes", {"run_id": "unit"}, config=config)
            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "ok")
            self.assertFalse(payload["private_core_included"])
            self.assertEqual(payload["workflow"]["id"], "microphone-to-minutes-post-capture")


if __name__ == "__main__":
    unittest.main()
