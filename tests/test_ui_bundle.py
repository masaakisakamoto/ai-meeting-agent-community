import json
import tempfile
import unittest
from pathlib import Path

from meeting_agent.core.transcript import parse_plain_text_transcript
from meeting_agent.intelligence.rule_minutes import RuleBasedMinutesGenerator
from meeting_agent.ui.demo_bundle import build_desktop_lite_bundle


class UIBundleTest(unittest.TestCase):
    def test_desktop_lite_bundle_contains_static_assets_and_demo_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            transcript = parse_plain_text_transcript(
                "[00:00:01] 佐藤: v0.3はDesktop Lite UIを追加することで決定します。\n"
                "[00:00:04] 鈴木: 山田さん、金曜までにREADME更新お願いします。",
                meeting_id="mtg_ui",
                title="UI demo",
            )
            minutes = RuleBasedMinutesGenerator().generate(transcript)
            paths = build_desktop_lite_bundle(transcript, tmp_path, minutes=minutes)

            for name in ["index.html", "styles.css", "app.js", "demo_data.js", "transcript.json", "minutes.json", "replay_events.json"]:
                self.assertIn(name, paths)
                self.assertTrue((tmp_path / name).exists())

            data_js = (tmp_path / "demo_data.js").read_text(encoding="utf-8")
            self.assertIn("window.MEETING_AGENT_DEMO", data_js)
            self.assertIn("mtg_ui", data_js)
            replay = json.loads((tmp_path / "replay_events.json").read_text(encoding="utf-8"))
            self.assertEqual(replay["events"][-1]["type"], "meeting_end")


if __name__ == "__main__":
    unittest.main()
