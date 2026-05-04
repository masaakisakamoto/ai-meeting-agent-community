import json
import tempfile
import unittest
from pathlib import Path

from meeting_agent.core.transcript import parse_plain_text_transcript
from meeting_agent.exporters.csv_exporter import ActionItemCSVExporter
from meeting_agent.exporters.html import HTMLExporter
from meeting_agent.intelligence.glossary import GlossaryEntry, apply_glossary
from meeting_agent.intelligence.rule_minutes import RuleBasedMinutesGenerator
from meeting_agent.intelligence.verifier import MinutesVerifier
from meeting_agent.quality.gates import run_minutes_quality_gate
from meeting_agent.storage.sqlite_store import SQLiteMeetingStore


class GlossaryExportStorageTest(unittest.TestCase):
    def _minutes_fixture(self):
        transcript = parse_plain_text_transcript(
            "\n".join(
                [
                    "[00:00:01] 佐藤: AIミーティングエージェントはMarkdown出力で進めることで決定します。",
                    "[00:00:10] 田中: 鈴木さん、来週中にタウリの音声取得を調査お願いします。",
                ]
            ),
            meeting_id="m1",
            title="demo",
        )
        corrected, report = apply_glossary(
            transcript,
            [
                GlossaryEntry(canonical="AI Meeting Agent", aliases=("AIミーティングエージェント",), type="product"),
                GlossaryEntry(canonical="Tauri", aliases=("タウリ",), type="technology"),
            ],
        )
        minutes = RuleBasedMinutesGenerator().generate(corrected)
        verification = MinutesVerifier().verify(corrected, minutes)
        return corrected, minutes, verification, report

    def test_glossary_canonicalizes_terms(self):
        transcript, _minutes, _verification, report = self._minutes_fixture()
        text = " ".join(s.text for s in transcript.segments)
        self.assertIn("AI Meeting Agent", text)
        self.assertIn("Tauri", text)
        self.assertEqual(report.total_replacements, 2)

    def test_html_and_csv_exporters(self):
        transcript, minutes, _verification, _report = self._minutes_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "minutes.html"
            csv_path = Path(tmp) / "actions.csv"
            HTMLExporter().export(transcript, minutes, html_path)
            ActionItemCSVExporter().export(transcript, minutes, csv_path)
            html = html_path.read_text(encoding="utf-8")
            csv_text = csv_path.read_text(encoding="utf-8")
            self.assertIn("href='#seg_0001'", html)
            self.assertIn("鈴木", csv_text)
            self.assertIn("Tauri", csv_text)

    def test_sqlite_store_and_quality_gate(self):
        transcript, minutes, verification, _report = self._minutes_fixture()
        quality = run_minutes_quality_gate(transcript, minutes, verification)
        self.assertEqual(quality.status, "pass")
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "meetings.sqlite"
            store = SQLiteMeetingStore(db)
            store.upsert_meeting(transcript, minutes)
            self.assertEqual(store.get_transcript("m1").meeting_id, "m1")
            self.assertIsNotNone(store.get_minutes("m1"))
            self.assertEqual(len(store.list_meetings()), 1)


if __name__ == "__main__":
    unittest.main()
