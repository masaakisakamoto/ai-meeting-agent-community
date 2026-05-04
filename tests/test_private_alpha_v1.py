from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from meeting_agent.audio.capture_plan import build_live_capture_plan
from meeting_agent.env.dev_environment import run_dev_environment_doctor
from meeting_agent.release.private_alpha import run_private_alpha_gate
from meeting_agent.desktop.bridge import BridgeConfig, handle_bridge_request


class PrivateAlphaV1Test(unittest.TestCase):
    def test_dev_environment_doctor_is_public_core_safe(self):
        report = run_dev_environment_doctor(root=Path.cwd())
        self.assertIn(report.status, {"pass", "warn"})
        self.assertFalse(report.private_core_included)
        self.assertTrue(any(check.id == "python_runtime" for check in report.checks))
        self.assertIn("publication-gate", " ".join(report.recommendations))

    def test_live_capture_plan_does_not_open_microphone(self):
        plan = build_live_capture_plan(out_dir="mic_live", duration_ms=3000)
        self.assertEqual(plan.status, "ready_for_dry_run")
        self.assertFalse(plan.private_core_included)
        self.assertIn("--live", plan.live_command)
        self.assertNotIn("--live", plan.dry_run_command)
        self.assertEqual(plan.safety_gate["live_requested"], False)

    def test_private_alpha_gate_keeps_publication_blocked(self):
        report = run_private_alpha_gate(root=Path.cwd(), run_tests=False)
        self.assertIn(report.status, {"pass", "warn"})
        self.assertIn("public_github_repository", report.blocked_modes)
        self.assertFalse(report.private_core_included)
        checks = {check.id: check.status for check in report.checks}
        self.assertEqual(checks["publication_hold"], "pass")

    def test_bridge_v1_routes_are_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = BridgeConfig(workspace=tmp)
            status, env = handle_bridge_request("GET", "/api/dev/environment", {}, config=config)
            self.assertEqual(status, 200)
            self.assertIn(env["status"], {"ok", "fail"})
            self.assertFalse(env["private_core_included"])
            status, plan = handle_bridge_request("GET", "/api/capture/plan?duration_ms=3000", {}, config=config)
            self.assertEqual(status, 200)
            self.assertEqual(plan["capture_plan"]["status"], "ready_for_dry_run")
            status, gate = handle_bridge_request("GET", "/api/private-alpha/gate", {}, config=config)
            self.assertEqual(status, 200)
            self.assertIn(gate["status"], {"ok", "fail"})
            self.assertFalse(gate["private_core_included"])


if __name__ == "__main__":
    unittest.main()
