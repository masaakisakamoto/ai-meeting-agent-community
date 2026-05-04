import tempfile
import unittest
from pathlib import Path

from meeting_agent.desktop.bridge import BridgeConfig, handle_bridge_request
from meeting_agent.release.evidence_export import (
    build_evidence_export_pack,
    build_screenshot_automation_pack,
    export_evidence_bundle,
    run_evidence_export_gate,
    run_screenshot_readiness_gate,
)


class EvidenceExportV22Test(unittest.TestCase):
    def test_evidence_export_pack_is_safe_and_writer_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "evidence_export_pack"
            report = build_evidence_export_pack(out_dir=out, root=tmp)
            self.assertEqual(report.status, "pass")
            self.assertFalse(report.opens_microphone)
            self.assertFalse(report.private_core_included)
            self.assertTrue((out / "README_SNIPPETS.md").exists())
            self.assertTrue((out / "scripts" / "02_export_evidence.sh").exists())

    def test_screenshot_pack_and_readiness_warn_without_curated_screenshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "screenshot_automation"
            report = build_screenshot_automation_pack(out_dir=out, root=tmp)
            self.assertIn(report.status, {"pass", "warn"})
            self.assertGreaterEqual(len(report.shotlist), 5)
            readiness = run_screenshot_readiness_gate(root=tmp, screenshot_dir="screenshots", demo_dir="demo_out")
            self.assertEqual(readiness.status, "warn")
            self.assertFalse(readiness.private_core_included)

    def test_export_bundle_and_gate_keep_publication_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "configs").mkdir()
            (root / "configs" / "publication_policy.json").write_text('{"public_oss_announcement_allowed": false}\n', encoding="utf-8")
            (root / "demo_out").mkdir()
            (root / "demo_out" / "minutes.html").write_text("<html>minutes</html>", encoding="utf-8")
            (root / "demo_out" / "publication_gate.md").write_text("# hold", encoding="utf-8")
            (root / "demo_out" / "desktop_alpha").mkdir()
            (root / "demo_out" / "desktop_alpha" / "app").mkdir()
            (root / "demo_out" / "desktop_alpha" / "app" / "index.html").write_text("<html>ui</html>", encoding="utf-8")
            report = export_evidence_bundle(root=root, out_dir="evidence_export")
            self.assertIn(report.status, {"pass", "warn"})
            self.assertTrue(report.publication_hold)
            gate = run_evidence_export_gate(root=root, export_dir="evidence_export")
            self.assertIn(gate.status, {"pass", "warn"})

    def test_bridge_evidence_export_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            status, payload = handle_bridge_request("GET", "/api/evidence/export-pack", {}, config=BridgeConfig(workspace=workspace))
            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "ok")
            status, payload = handle_bridge_request("GET", "/api/screenshots/automation-pack", {}, config=BridgeConfig(workspace=workspace))
            self.assertEqual(status, 200)
            self.assertIn(payload["status"], {"ok", "warn"})
            status, payload = handle_bridge_request("GET", "/api/evidence/export-gate", {}, config=BridgeConfig(workspace=workspace))
            self.assertEqual(status, 200)
            self.assertIn(payload["status"], {"ok", "fail"})


if __name__ == "__main__":
    unittest.main()
