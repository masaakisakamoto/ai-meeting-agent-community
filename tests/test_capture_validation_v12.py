from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from meeting_agent.audio.validation_pack import build_capture_validation_pack, evaluate_capture_validation_run
from meeting_agent.cli import main
from meeting_agent.providers.audio import AudioCaptureConfig, SimulatedAudioCaptureProvider
from meeting_agent.audio.session import capture_session_to_wav
from meeting_agent.audio.live_guard import evaluate_recording_safety_gate, write_recording_safety_gate_report


class CaptureValidationV12Tests(unittest.TestCase):
    def test_validation_pack_is_safe_and_writes_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pack"
            report = build_capture_validation_pack(out_dir=out, duration_ms=3000)
            self.assertIn(report.status, {"pass", "warn"})
            self.assertFalse(report.private_core_included)
            self.assertTrue((out / "README.md").exists())
            self.assertTrue((out / "scripts" / "01_dry_run.sh").exists())
            manifest = json.loads((out / "capture_validation_manifest.json").read_text())
            self.assertFalse(manifest["opens_microphone"])
            self.assertIn("02_live_capture", manifest["commands"])

    def test_validation_run_flags_missing_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = evaluate_capture_validation_run(mic_dir=Path(tmp) / "missing")
            self.assertEqual(report.status, "fail")
            self.assertTrue(any(check.id == "audio_wav" and check.status == "fail" for check in report.checks))

    def test_validation_run_accepts_simulated_capture_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mic = Path(tmp) / "mic"
            mic.mkdir()
            provider = SimulatedAudioCaptureProvider(total_ms=1000)
            capture_session_to_wav(provider, AudioCaptureConfig(device_id="simulated:microphone", chunk_ms=250), session_id="sim", wav_path=mic / "audio.wav", manifest_path=mic / "audio_session.json")
            safety = evaluate_recording_safety_gate(live_requested=False, publication_hold=True)
            write_recording_safety_gate_report(safety, out_json=mic / "recording_safety_gate.json", out_md=mic / "recording_safety_gate.md")
            (mic / "audit.jsonl").write_text('{"event":"test"}\n', encoding="utf-8")
            (mic / "microphone_alpha.json").write_text('{"status":"pass","private_core_included":false}\n', encoding="utf-8")
            report = evaluate_capture_validation_run(mic_dir=mic)
            self.assertIn(report.status, {"pass", "warn"})
            self.assertFalse(report.private_core_included)
            self.assertTrue(any(check.id == "audio_quality" for check in report.checks))

    def test_cli_validation_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pack"
            code = main(["capture-validation-pack", "--out-dir", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue((out / "capture_validation_pack.md").exists())


if __name__ == "__main__":
    unittest.main()
