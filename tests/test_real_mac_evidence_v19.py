from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from meeting_agent.release.evidence_collection import build_real_mac_evidence_pack, collect_real_mac_evidence


class RealMacEvidenceCollectionTest(unittest.TestCase):
    def test_pack_is_safe_and_contains_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = build_real_mac_evidence_pack(out_dir=Path(tmp) / "pack")
            self.assertIn(report.status, {"pass", "warn"})
            self.assertFalse(report.opens_microphone)
            self.assertFalse(report.private_core_included)
            self.assertTrue((Path(tmp) / "pack" / "scripts" / "08_collect_evidence.sh").exists())
            manifest = json.loads((Path(tmp) / "pack" / "real_mac_evidence_manifest.json").read_text())
            self.assertFalse(manifest["opens_microphone"])
            self.assertTrue(manifest["publication_hold"])

    def test_collect_warns_until_required_live_artifacts_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "configs").mkdir()
            (root / "configs" / "publication_policy.json").write_text(
                json.dumps({
                    "current_stage": "private_development",
                    "target_public_stage": "public_alpha",
                    "public_oss_announcement_allowed": False,
                    "allowed_modes": ["local_development"],
                    "blocked_modes": ["public_github_repository"],
                    "minimum_public_exit_criteria": [],
                    "hold_reason": "test hold",
                }),
                encoding="utf-8",
            )
            report = collect_real_mac_evidence(root=root, evidence_dir=root / "evidence", copy_artifacts=False)
            self.assertEqual(report.status, "warn")
            self.assertFalse(report.private_core_included)
            self.assertIn("audio_wav", report.summary["required_missing"])
            self.assertTrue((root / "evidence" / "real_mac_evidence.json").exists())


if __name__ == "__main__":
    unittest.main()
