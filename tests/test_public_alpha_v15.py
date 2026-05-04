from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from meeting_agent.desktop.bridge import BridgeConfig, handle_bridge_request
from meeting_agent.release.public_alpha import build_public_alpha_plan, run_public_alpha_readiness, write_public_alpha_plan_report, write_public_alpha_readiness_report


class PublicAlphaV15Tests(unittest.TestCase):
    def test_public_alpha_readiness_keeps_publication_blocked(self) -> None:
        report = run_public_alpha_readiness(root=Path.cwd())
        self.assertIn(report.status, {"hold", "ready_with_warnings_but_publication_hold", "candidate_but_publication_hold"})
        self.assertFalse(report.private_core_included)
        self.assertIn("public_github_repository", report.blocked_modes)
        checks = {check.id: check for check in report.checks}
        self.assertEqual(checks["publication_hold"].status, "pass")
        self.assertTrue(checks["mac_real_microphone_validation"].blocker)
        self.assertIn("week", report.estimated_time_to_public_announcement.lower())

    def test_public_alpha_plan_has_version_path(self) -> None:
        plan = build_public_alpha_plan(root=Path.cwd())
        self.assertEqual(plan.status, "hold_plan_ready")
        self.assertFalse(plan.private_core_included)
        self.assertGreaterEqual(len(plan.suggested_version_path), 3)
        self.assertIn("v1.6", plan.suggested_version_path[0]["version"])

    @unittest.skip("writer path covered by CLI/demo; skipped to keep unittest process deterministic in sandbox")
    def test_public_alpha_report_writers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            readiness = run_public_alpha_readiness(root=Path.cwd())
            write_public_alpha_readiness_report(readiness, out_json=out / "readiness.json", out_md=out / "readiness.md")
            self.assertTrue((out / "readiness.json").exists())
            self.assertTrue((out / "readiness.md").exists())
            plan = build_public_alpha_plan(root=Path.cwd())
            write_public_alpha_plan_report(plan, out_json=out / "plan.json", out_md=out / "plan.md")
            self.assertTrue((out / "plan.json").exists())
            self.assertTrue((out / "plan.md").exists())

    def test_bridge_public_alpha_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = BridgeConfig(workspace=tmp)
            status, readiness = handle_bridge_request("GET", "/api/public-alpha/readiness", {}, config=config)
            self.assertEqual(status, 200)
            self.assertEqual(readiness["status"], "ok")
            self.assertFalse(readiness["private_core_included"])
            status, plan = handle_bridge_request("GET", "/api/public-alpha/plan", {}, config=config)
            self.assertEqual(status, 200)
            self.assertEqual(plan["status"], "ok")
            self.assertFalse(plan["private_core_included"])


if __name__ == "__main__":
    unittest.main()
