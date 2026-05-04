from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from meeting_agent.audio.wav_io import write_wav_from_chunks
from meeting_agent.cli import main
from meeting_agent.desktop.bridge import BridgeConfig, handle_bridge_request
from meeting_agent.providers.audio import AudioCaptureConfig, SimulatedAudioCaptureProvider
from meeting_agent.workflows.asr_validation import build_asr_validation_pack, run_asr_validation


class ASRValidationV13Tests(unittest.TestCase):
    def _make_audio(self, root: Path) -> tuple[Path, Path]:
        provider = SimulatedAudioCaptureProvider(total_ms=1000)
        config = AudioCaptureConfig(device_id="simulated:microphone", sample_rate_hz=16000, channels=1, chunk_ms=250)
        chunks = list(provider.capture(config, session_id="asr_validation"))
        audio = root / "audio.wav"
        write_wav_from_chunks(chunks, audio)
        sidecar = root / "audio.transcript.txt"
        sidecar.write_text(
            "[00:00:00 - 00:00:01] 佐藤: v1.4ではASR検証パックを追加することで決定します。\n"
            "[00:00:01 - 00:00:02] 田中: 音声認識結果のCERとWERを確認します。\n",
            encoding="utf-8",
        )
        return audio, sidecar

    def test_asr_validation_pack_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pack"
            report = build_asr_validation_pack(out_dir=out)
            self.assertIn(report.status, {"pass", "warn"})
            self.assertFalse(report.private_core_included)
            self.assertTrue((out / "asr_validation_manifest.json").exists())
            self.assertTrue((out / "scripts" / "01_sidecar_validation.sh").exists())

    def test_sidecar_asr_validation_writes_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio, sidecar = self._make_audio(root)
            out = root / "asr_out"
            report = run_asr_validation(audio_path=audio, out_dir=out, provider="sidecar", sidecar_path=sidecar, reference_path=sidecar)
            self.assertIn(report.status, {"pass", "warn"})
            self.assertFalse(report.private_core_included)
            self.assertTrue((out / "transcript.asr.json").exists())
            self.assertTrue((out / "metrics.json").exists())
            self.assertEqual(report.metrics["cer"], 0.0)

    def test_faster_whisper_dry_run_does_not_transcribe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio, _sidecar = self._make_audio(root)
            out = root / "fw_dry"
            report = run_asr_validation(audio_path=audio, out_dir=out, provider="faster-whisper", dry_run=True)
            self.assertIn(report.status, {"pass", "warn", "fail"})
            self.assertTrue(report.dry_run)
            self.assertFalse((out / "transcript.asr.json").exists())
            self.assertTrue((out / "asr_validation_report.md").exists())

    def test_cli_asr_validation_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio, sidecar = self._make_audio(root)
            out = root / "cli_asr"
            code = main(["asr-validation-run", "--audio-path", str(audio), "--provider", "sidecar", "--sidecar", str(sidecar), "--reference", str(sidecar), "--out-dir", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue((out / "asr_validation_report.json").exists())

    def test_bridge_asr_validation_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_audio(root)
            config = BridgeConfig(workspace=root)
            status, pack = handle_bridge_request("GET", "/api/asr/validation-pack?provider=sidecar", {}, config=config)
            self.assertEqual(status, 200)
            self.assertIn(pack["status"], {"ok", "fail"})
            status, payload = handle_bridge_request("POST", "/api/asr/validation-run", {"run_id": "unit", "provider": "sidecar"}, config=config)
            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "ok")
            self.assertFalse(payload["private_core_included"])
            self.assertEqual(payload["workflow"]["id"], "asr-validation")


if __name__ == "__main__":
    unittest.main()
