from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from meeting_agent.desktop.bridge import BridgeConfig, handle_bridge_request
from meeting_agent.release.public_alpha_candidate import (
    build_public_alpha_candidate_pack,
    run_public_alpha_candidate_gate,
)


class PublicAlphaCandidateTests(unittest.TestCase):
    def test_candidate_pack_is_private_and_does_not_open_microphone(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "configs").mkdir()
            (root / "configs" / "publication_policy.json").write_text(
                json.dumps({
                    "current_stage": "private_development",
                    "target_public_stage": "public_alpha",
                    "public_oss_announcement_allowed": False,
                    "allowed_modes": ["local_development", "private_repository"],
                    "blocked_modes": ["public_github_repository", "sns_announcement"],
                    "minimum_public_exit_criteria": ["maintainer approval"],
                    "hold_reason": "private until public alpha",
                }),
                encoding="utf-8",
            )
            report = build_public_alpha_candidate_pack(out_dir=root / "candidate", root=root)
            self.assertEqual(report.status, "pass")
            self.assertFalse(report.opens_microphone)
            self.assertFalse(report.private_core_included)
            self.assertTrue((root / "candidate" / "PUBLIC_ALPHA_CANDIDATE_README.md").exists())
            self.assertTrue((root / "candidate" / "scripts" / "01_run_final_private_gates.sh").exists())

    def test_candidate_gate_stays_on_hold_without_real_evidence(self):
        report = build_public_alpha_candidate_pack(out_dir="/tmp/meeting-agent-test-candidate-pack")
        gate = run_public_alpha_candidate_gate(candidate_dir="/tmp/meeting-agent-test-candidate-pack")
        self.assertIn(gate.status, {"hold_missing_candidate_evidence", "candidate_ready_but_publication_hold", "candidate_policy_unlocked_review_required"})
        self.assertIsInstance(gate.publication_hold, bool)
        self.assertFalse(gate.private_core_included)
        self.assertIn("real_mac_evidence_collection", {check.id for check in gate.checks})

    def test_bridge_candidate_routes_are_private_safe(self):
        with tempfile.TemporaryDirectory() as td:
            config = BridgeConfig(workspace=Path(td), port=0)
            status, pack = handle_bridge_request("GET", "/api/public-alpha/candidate-pack", {}, config=config)
            self.assertEqual(status, 200)
            self.assertFalse(pack["private_core_included"])
            self.assertEqual(pack["public_alpha_candidate_pack"]["status"], "pass")
            status, gate = handle_bridge_request("GET", "/api/public-alpha/candidate-gate", {}, config=config)
            self.assertEqual(status, 200)
            self.assertFalse(gate["private_core_included"])
            self.assertIn(gate["public_alpha_candidate_gate"]["status"], {"hold_missing_candidate_evidence", "candidate_ready_but_publication_hold", "candidate_policy_unlocked_review_required"})


if __name__ == "__main__":
    unittest.main()
