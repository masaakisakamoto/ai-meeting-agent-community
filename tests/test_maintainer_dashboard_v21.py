from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from meeting_agent.desktop.bridge import BridgeConfig, handle_bridge_request
from meeting_agent.release.maintainer_dashboard import build_maintainer_dashboard, build_maintainer_review_pack


class MaintainerDashboardTests(unittest.TestCase):
    def test_maintainer_review_pack_is_private_safe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = build_maintainer_review_pack(out_dir=root / "review", root=root)
            self.assertEqual(report.status, "pass")
            self.assertFalse(report.opens_microphone)
            self.assertFalse(report.private_core_included)
            self.assertTrue((root / "review" / "MAINTAINER_DECISION_MATRIX.md").exists())
            self.assertTrue((root / "review" / "scripts" / "02_build_dashboard.sh").exists())

    def test_maintainer_dashboard_writes_html_and_keeps_hold(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "dashboard"
            report = build_maintainer_dashboard(root=Path.cwd(), dashboard_dir=out)
            self.assertIn(report.status, {"hold", "candidate_review_ready", "blocked_private_core", "candidate_policy_unlocked_review_required"})
            self.assertIsInstance(report.publication_hold, bool)
            self.assertFalse(report.private_core_included)
            self.assertTrue((out / "maintainer_dashboard.html").exists())
            self.assertIn("public_alpha_candidate_gate", {check.id for check in report.checks})
            self.assertIn("real_mac_evidence", {check.id for check in report.checks})

    def test_bridge_maintainer_routes_are_private_safe(self):
        with tempfile.TemporaryDirectory() as td:
            config = BridgeConfig(workspace=Path(td), port=0)
            status, pack = handle_bridge_request("GET", "/api/maintainer/review-pack", {}, config=config)
            self.assertEqual(status, 200)
            self.assertFalse(pack["private_core_included"])
            self.assertEqual(pack["maintainer_review_pack"]["status"], "pass")
            status, dashboard = handle_bridge_request("GET", "/api/maintainer/dashboard", {}, config=config)
            self.assertEqual(status, 200)
            self.assertFalse(dashboard["private_core_included"])
            self.assertIn(dashboard["maintainer_dashboard"]["status"], {"hold", "candidate_review_ready", "blocked_private_core", "candidate_policy_unlocked_review_required"})


if __name__ == "__main__":
    unittest.main()
