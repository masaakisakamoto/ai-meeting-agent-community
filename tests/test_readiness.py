from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from meeting_agent.release.readiness import run_readiness_checks


class TestReadiness(unittest.TestCase):
    def test_current_repository_is_release_ready_enough(self) -> None:
        root = Path(__file__).resolve().parents[1]
        report = run_readiness_checks(root)
        self.assertGreaterEqual(report.score, 0.92)
        self.assertEqual(report.status, "pass")

    def test_missing_required_files_blocks_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("demo", encoding="utf-8")
            report = run_readiness_checks(root)
            self.assertEqual(report.status, "needs_work")
            self.assertTrue(any(c.id == "required_public_files" and c.status == "fail" for c in report.checks))

    def test_secret_like_pattern_blocks_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            required = [
                "README.md",
                "LICENSE",
                "NOTICE",
                "THIRD_PARTY_NOTICES.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "TRADEMARK.md",
                "docs/ARCHITECTURE.md",
                "docs/OPEN_CORE_STRATEGY.md",
                "docs/PRIVATE_CORE_BOUNDARIES.md",
                "docs/OSS_COMPLIANCE.md",
                "docs/ROADMAP.md",
            ]
            for rel in required:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("Quality Engine Model Router Verifier Private", encoding="utf-8")
            (root / "pyproject.toml").write_text("Apache-2.0 meeting-agent requires-python", encoding="utf-8")
            (root / "tests").mkdir()
            for i in range(5):
                (root / "tests" / f"test_{i}.py").write_text("def test_ok(): pass", encoding="utf-8")
            (root / "examples").mkdir()
            (root / "examples" / "sample_meeting_ja.txt").write_text("これは十分な長さの日本語サンプルです。" * 10, encoding="utf-8")
            (root / "leak.py").write_text("api_" + "key = '" + "sk-" + "THIS_SHOULD_NOT_BE_PUBLIC_1234567890'", encoding="utf-8")
            report = run_readiness_checks(root)
            self.assertEqual(report.status, "needs_work")
            self.assertTrue(any(c.id == "private_leakage_scan" and c.status == "fail" for c in report.checks))


if __name__ == "__main__":
    unittest.main()
