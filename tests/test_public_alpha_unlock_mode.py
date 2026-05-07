from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from meeting_agent.desktop.bridge import BridgeConfig, handle_bridge_request
from meeting_agent.release.private_alpha import run_private_alpha_gate
from meeting_agent.release.public_alpha import build_public_alpha_plan, run_public_alpha_readiness
from meeting_agent.release.public_alpha_candidate import build_public_alpha_candidate_pack, run_public_alpha_candidate_gate
from meeting_agent.release.publication import run_publication_gate


@contextmanager
def temporary_public_alpha_unlock():
    policy_path = Path("configs/publication_policy.json")
    original = policy_path.read_text(encoding="utf-8")
    data = json.loads(original)
    data["current_stage"] = "public_alpha"
    data["public_oss_announcement_allowed"] = True
    data["hold_reason"] = "Temporary unlock-mode test only."
    data["allowed_modes"] = [
        "local_development",
        "private_repository",
        "private_portfolio_review",
        "controlled_technical_review",
        "private_alpha_hardware_validation",
        "public_github_repository",
        "public_alpha_release",
    ]
    data["blocked_modes"] = ["commercial_landing_page"]
    try:
        policy_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        yield
    finally:
        policy_path.write_text(original, encoding="utf-8")


class PublicAlphaUnlockModeTests(unittest.TestCase):
    def test_publication_gate_reports_ready_when_policy_is_unlocked(self) -> None:
        with temporary_public_alpha_unlock():
            report = run_publication_gate(Path.cwd())
            self.assertEqual(report.status, "ready")
            self.assertFalse(report.private_core_included)
            self.assertIn("public_github_repository", report.allowed_modes)

    def test_private_alpha_gate_is_advisory_in_unlocked_mode(self) -> None:
        with temporary_public_alpha_unlock():
            report = run_private_alpha_gate(root=Path.cwd(), run_tests=False)
            self.assertIn(report.status, {"pass", "warn"})
            checks = {check.id: check.status for check in report.checks}
            self.assertEqual(checks["publication_hold"], "warn")
            self.assertFalse(report.private_core_included)

    def test_candidate_gate_accepts_unlocked_review_required_status(self) -> None:
        with temporary_public_alpha_unlock():
            with tempfile.TemporaryDirectory() as td:
                candidate_dir = Path(td) / "candidate"
                build_public_alpha_candidate_pack(out_dir=candidate_dir, root=Path.cwd())
                report = run_public_alpha_candidate_gate(root=Path.cwd(), candidate_dir=candidate_dir)
                self.assertEqual(report.status, "candidate_policy_unlocked_review_required")
                self.assertFalse(report.publication_hold)
                self.assertFalse(report.private_core_included)

    def test_public_alpha_routes_remain_serializable_in_unlocked_mode(self) -> None:
        with temporary_public_alpha_unlock():
            with tempfile.TemporaryDirectory() as td:
                config = BridgeConfig(workspace=Path(td), port=0)

                status, readiness = handle_bridge_request("GET", "/api/public-alpha/readiness", {}, config=config)
                self.assertEqual(status, 200)
                self.assertIn(readiness["status"], {"ok", "fail"})
                self.assertFalse(readiness["private_core_included"])

                status, plan = handle_bridge_request("GET", "/api/public-alpha/plan", {}, config=config)
                self.assertEqual(status, 200)
                self.assertIn(plan["status"], {"ok", "fail"})
                self.assertFalse(plan["private_core_included"])

                status, gate = handle_bridge_request("GET", "/api/public-alpha/candidate-gate", {}, config=config)
                self.assertEqual(status, 200)
                self.assertEqual(gate["status"], "ok")
                self.assertFalse(gate["private_core_included"])

    def test_public_alpha_readiness_and_plan_do_not_include_private_core(self) -> None:
        with temporary_public_alpha_unlock():
            readiness = run_public_alpha_readiness(root=Path.cwd())
            self.assertFalse(readiness.private_core_included)
            self.assertIn(readiness.status, {"blocked", "hold", "ready_with_warnings_but_publication_hold", "candidate_but_publication_hold"})

            plan = build_public_alpha_plan(root=Path.cwd())
            self.assertFalse(plan.private_core_included)
            self.assertIn(plan.status, {"blocked", "hold_plan_ready", "ready"})


if __name__ == "__main__":
    unittest.main()
