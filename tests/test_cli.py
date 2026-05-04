import json
import tempfile
import unittest
from pathlib import Path

from meeting_agent.cli import main


class CLITest(unittest.TestCase):
    def test_ingest_and_minutes_commands(self):
        sample = Path(__file__).resolve().parents[1] / "examples" / "sample_meeting_ja.txt"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            transcript_path = out / "meeting.json"
            minutes_json = out / "minutes.json"
            minutes_md = out / "minutes.md"
            self.assertEqual(main(["ingest", str(sample), "--out", str(transcript_path)]), 0)
            self.assertEqual(
                main([
                    "minutes",
                    str(transcript_path),
                    "--out-json",
                    str(minutes_json),
                    "--out-md",
                    str(minutes_md),
                ]),
                0,
            )
            self.assertTrue((out / "meeting.json").exists())
            self.assertTrue((out / "minutes.json").exists())
            self.assertTrue((out / "minutes.md").exists())
            data = json.loads(minutes_json.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(data["decisions"]), 1)


if __name__ == "__main__":
    unittest.main()
