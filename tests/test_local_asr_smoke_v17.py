from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from meeting_agent.audio.wav_io import write_wav_from_chunks
from meeting_agent.cli import main
from meeting_agent.desktop.bridge import BridgeConfig, handle_bridge_request
from meeting_agent.providers.audio import AudioCaptureConfig, SimulatedAudioCaptureProvider
from meeting_agent.workflows.local_asr_smoke import (
    build_local_asr_smoke_pack,
    evaluate_local_asr_smoke_gate,
    run_local_asr_smoke,
)


class LocalASRSmokeV17Tests(unittest.TestCase):
    def _make_audio(self, root: Path) -> tuple[Path, Path]:
        provider = SimulatedAudioCaptureProvider(total_ms=1000)
        config = AudioCaptureConfig(device_id="simulated:microphone", sample_rate_hz=16000, channels=1, chunk_ms=250)
        audio = root / "audio.wav"
        write_wav_from_chunks(list(provider.capture(config, session_id="local_asr_smoke")), audio)
        sidecar = root / "audio.transcript.txt"
        sidecar.write_text(
            "[00:00:00 - 00:00:01] 佐藤: v1.7ではローカルASRスモークを確認することで決定します。\n"
            "[00:00:01 - 00:00:02] 田中: 鈴木さん、金曜までにASRレポートを確認お願いします。\n",
            encoding="utf-8",
        )
        return audio, sidecar

    def test_local_asr_smoke_pack_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pack"
            report = build_local_asr_smoke_pack(out_dir=out)
            self.assertIn(report.status, {"pass", "warn"})
            self.assertFalse(report.opens_microphone)
            self.assertFalse(report.private_core_included)
            self.assertTrue((out / "local_asr_smoke_manifest.json").exists())
            self.assertTrue((out / "scripts" / "01_sidecar_smoke.sh").exists())

    def test_local_asr_smoke_run_generates_sidecar_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio, sidecar = self._make_audio(root)
            out = root / "local_asr_smoke"
            report = run_local_asr_smoke(audio_path=audio, out_dir=out, sidecar_path=sidecar, reference_path=sidecar)
            self.assertIn(report.status, {"pass", "warn"})
            self.assertFalse(report.private_core_included)
            self.assertTrue((out / "sidecar_asr_minutes" / "minutes.html").exists())
            self.assertTrue((out / "local_asr_smoke_report.json").exists())

    def test_local_asr_smoke_gate_accepts_private_preview_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio, sidecar = self._make_audio(root)
            out = root / "local_asr_smoke"
            run_local_asr_smoke(audio_path=audio, out_dir=out, sidecar_path=sidecar, reference_path=sidecar)
            gate = evaluate_local_asr_smoke_gate(smoke_dir=out, require_real_asr=False)
            self.assertIn(gate.status, {"pass", "warn"})
            self.assertFalse(gate.private_core_included)

    def test_cli_and_bridge_local_asr_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio, sidecar = self._make_audio(root)
            out = root / "cli_local_asr"
            code = main([
                "local-asr-smoke-run",
                "--audio-path", str(audio),
                "--sidecar", str(sidecar),
                "--reference", str(sidecar),
                "--out-dir", str(out),
            ])
            self.assertEqual(code, 0)
            self.assertTrue((out / "local_asr_smoke_report.json").exists())

            config = BridgeConfig(workspace=root)
            status, pack = handle_bridge_request("GET", "/api/local-asr/smoke-pack", {}, config=config)
            self.assertEqual(status, 200)
            self.assertIn(pack["status"], {"ok", "fail"})
            status, payload = handle_bridge_request("POST", "/api/local-asr/smoke-run", {"run_id": "unit", "mode": "sidecar"}, config=config)
            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["workflow"]["id"], "local-asr-smoke")
            self.assertFalse(payload["private_core_included"])


if __name__ == "__main__":
    unittest.main()
