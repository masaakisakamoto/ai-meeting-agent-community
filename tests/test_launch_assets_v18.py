from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from meeting_agent.desktop.bridge import DesktopBridgeConfig, handle_bridge_request
from meeting_agent.release.launch_assets import build_launch_asset_pack, run_launch_polish_check


class LaunchAssetsV18Test(unittest.TestCase):
    def test_launch_asset_pack_generates_required_private_review_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "configs").mkdir()
            (root / "configs" / "publication_policy.json").write_text("{}", encoding="utf-8")
            (root / "README.md").write_text("Private Developer Preview Desktop Alpha publication-gate", encoding="utf-8")
            report = build_launch_asset_pack(root=root, out_dir="launch_assets")
            self.assertEqual(report.status, "pass")
            self.assertFalse(report.private_core_included)
            self.assertTrue((root / "launch_assets" / "README_PUBLIC_ALPHA_DRAFT.md").exists())
            self.assertTrue((root / "launch_assets" / "scripts" / "verify_private_hold.sh").exists())

    def test_launch_polish_check_keeps_publication_private_without_screenshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "configs").mkdir()
            (root / "configs" / "publication_policy.json").write_text("{}", encoding="utf-8")
            (root / "README.md").write_text("Private Developer Preview Desktop Alpha publication-gate", encoding="utf-8")
            build_launch_asset_pack(root=root, out_dir="launch_assets")
            report = run_launch_polish_check(root=root, launch_assets_dir="launch_assets")
            self.assertIn(report.status, {"pass", "warn"})
            self.assertFalse(report.private_core_included)
            self.assertIn("screenshots_curated", report.missing_or_warn_items)

    def test_bridge_launch_routes_are_public_core_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = DesktopBridgeConfig(workspace=Path(tmp), port=0)
            status, payload = handle_bridge_request("GET", "/api/launch/assets-pack", config=config)
            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "ok")
            self.assertFalse(payload["private_core_included"])
            status, payload = handle_bridge_request("GET", "/api/launch/polish-check", config=config)
            self.assertEqual(status, 200)
            self.assertFalse(payload["private_core_included"])


if __name__ == "__main__":
    unittest.main()
