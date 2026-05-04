from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from meeting_agent.audio import run_microphone_alpha_doctor, run_microphone_alpha_recording, microphone_setup_guide
from meeting_agent.desktop.bridge import DesktopBridgeConfig, handle_bridge_request


class MicrophoneAlphaTest(unittest.TestCase):
    def test_microphone_doctor_is_safe_and_public_core_only(self):
        report = run_microphone_alpha_doctor()
        self.assertIn(report.status, {"pass", "warn", "fail"})
        self.assertFalse(report.private_core_included)
        self.assertTrue(any(check.id == "python_version" for check in report.checks))
        self.assertIn("Python", report.to_markdown())

    def test_microphone_alpha_dry_run_writes_reports_without_opening_mic(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_microphone_alpha_recording(out_dir=tmp, dry_run=True)
            self.assertIn(report.mode, {"dry_run"})
            self.assertFalse(report.private_core_included)
            self.assertTrue((Path(tmp) / "microphone_alpha.json").exists())
            self.assertTrue((Path(tmp) / "microphone_alpha.md").exists())

    def test_bridge_microphone_routes_are_dry_run_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = DesktopBridgeConfig(workspace=tmp)
            status, payload = handle_bridge_request("GET", "/api/microphone/doctor", {}, config=config)
            self.assertEqual(status, 200)
            self.assertIn(payload["status"], {"ok", "fail"})
            self.assertFalse(payload["microphone"]["private_core_included"])
            status, payload = handle_bridge_request("POST", "/api/workflows/microphone-alpha", {"duration_ms": 1000}, config=config)
            self.assertEqual(status, 200)
            self.assertIn(payload["workflow"]["mode"], {"dry_run"})
            self.assertFalse(payload["workflow"]["private_core_included"])

    def test_setup_guide_contains_python312(self):
        guide = microphone_setup_guide()
        self.assertIn("python3.12", guide)
        self.assertIn(".[audio]", guide)


if __name__ == "__main__":
    unittest.main()

class RecordingSafetyGateTest(unittest.TestCase):
    def test_live_capture_is_blocked_without_explicit_consent(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_microphone_alpha_recording(out_dir=tmp, dry_run=False, duration_ms=1000)
            self.assertEqual(report.mode, "blocked_live_capture")
            self.assertEqual(report.status, "fail")
            self.assertFalse(report.safety_gate["live_allowed"])
            self.assertTrue((Path(tmp) / "recording_safety_gate.json").exists())
            self.assertTrue((Path(tmp) / "audit.jsonl").exists())

    def test_recording_safety_gate_bridge_route_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = DesktopBridgeConfig(workspace=tmp)
            status, payload = handle_bridge_request("POST", "/api/recording/safety-gate", {"duration_ms": 1000}, config=config)
            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "ok")
            self.assertFalse(payload["private_core_included"])
            self.assertFalse(payload["recording_safety_gate"]["live_requested"])

    def test_bridge_real_microphone_request_without_confirmation_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = DesktopBridgeConfig(workspace=tmp)
            status, payload = handle_bridge_request(
                "POST",
                "/api/workflows/microphone-alpha",
                {"real_capture": True, "duration_ms": 1000},
                config=config,
            )
            self.assertEqual(status, 200)
            self.assertEqual(payload["workflow"]["mode"], "blocked_live_capture")
            self.assertEqual(payload["workflow"]["status"], "fail")
            self.assertFalse(payload["workflow"]["private_core_included"])
