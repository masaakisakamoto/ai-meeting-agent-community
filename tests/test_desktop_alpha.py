from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from meeting_agent.core.transcript import parse_plain_text_transcript
from meeting_agent.desktop.bridge import DesktopBridgeConfig, handle_bridge_request
from meeting_agent.desktop.workspace import DesktopAlphaManager


class DesktopAlphaTest(unittest.TestCase):
    def test_desktop_alpha_workspace_creates_manifest_and_ui(self):
        transcript = parse_plain_text_transcript(
            "[00:00:01] 佐藤: v0.6ではDesktop Alphaを進めることで決定します。",
            meeting_id="mtg_desktop_test",
            title="Desktop Alpha Test",
        )
        with tempfile.TemporaryDirectory() as tmp:
            manager = DesktopAlphaManager(tmp)
            paths = manager.initialize(transcript)
            self.assertTrue(paths["index.html"].exists())
            manifest = json.loads((Path(tmp) / "desktop_alpha_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], "desktop-alpha-manifest/v1")
            self.assertIn("excluded_private_core", manifest["public_boundary"])
            self.assertTrue((Path(tmp) / "launch_desktop_alpha.py").exists())

    def test_desktop_alpha_workspace_contract_is_public_core_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = DesktopAlphaManager(tmp)
            manager.initialize()
            manifest = json.loads((Path(tmp) / "desktop_alpha_manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest.get("private_core_included", False))
            self.assertIn("excluded_private_core", manifest["public_boundary"])
            self.assertTrue((Path(tmp) / "desktop_lite" / "index.html").exists())

    def test_local_bridge_health_endpoint(self):
        transcript = parse_plain_text_transcript(
            "[00:00:01] 佐藤: Bridgeを確認します。",
            meeting_id="mtg_bridge_test",
            title="Bridge Test",
        )
        with tempfile.TemporaryDirectory() as tmp:
            manager = DesktopAlphaManager(tmp)
            manager.initialize(transcript)
            config = DesktopBridgeConfig(workspace=Path(tmp), static_dir=Path(tmp) / "desktop_lite", port=0)
            status, payload = handle_bridge_request("GET", "/health", config=config)
            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "ok")
            self.assertFalse(payload["private_core_included"])


if __name__ == "__main__":
    unittest.main()
