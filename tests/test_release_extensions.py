from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from meeting_agent.core.plugin_manifest import PluginManifest, load_manifest, save_manifest
from meeting_agent.release.sbom import generate_sbom


class ReleaseExtensionsTest(unittest.TestCase):
    def test_plugin_manifest_validation_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plugin.json"
            manifest = PluginManifest(
                id="export.markdown",
                name="Markdown Exporter",
                version="1.0.0",
                kind="exporter",
                entrypoint="meeting_agent.exporters.markdown:MarkdownExporter",
                license="Apache-2.0",
                capabilities=("minutes", "evidence"),
            )
            save_manifest(manifest, path)
            loaded = load_manifest(path)
            self.assertEqual(loaded.id, "export.markdown")
            self.assertFalse(loaded.validate(community_only=True))

    def test_community_manifest_rejects_private_core_requirement(self) -> None:
        manifest = PluginManifest(
            id="quality.private",
            name="Private Quality Plugin",
            version="0.3.0",
            kind="minutes_generator",
            entrypoint="private.module:Plugin",
            license="Commercial",
            requires_private_core=True,
        )
        self.assertTrue(manifest.validate(community_only=True))

    def test_sbom_reads_project_metadata(self) -> None:
        root = Path(__file__).resolve().parents[1]
        sbom = generate_sbom(root)
        self.assertEqual(sbom.name, "ai-meeting-agent-community")
        from meeting_agent import __version__
        self.assertEqual(sbom.version, __version__)
        self.assertGreaterEqual(len(sbom.notes), 1)


if __name__ == "__main__":
    unittest.main()
