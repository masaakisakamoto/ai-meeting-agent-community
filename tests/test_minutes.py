import unittest

from meeting_agent.core.transcript import parse_plain_text_transcript
from meeting_agent.intelligence.rule_minutes import RuleBasedMinutesGenerator


class RuleMinutesTest(unittest.TestCase):
    def test_extracts_decision_action_question_and_risk(self):
        transcript = parse_plain_text_transcript(
            "\n".join(
                [
                    "[00:00:01] 佐藤: v0.1はMarkdown出力で進めることで決定します。",
                    "[00:00:10] 田中: 鈴木さん、来週中に音声取得を調査お願いします。",
                    "[00:00:20] 鈴木: 無料版でどこまで出すかは未定です。",
                    "[00:00:30] 佐藤: AGPLコードを混ぜると商用化で問題になるリスクがあります。",
                ]
            ),
            meeting_id="m1",
            title="demo",
        )
        minutes = RuleBasedMinutesGenerator().generate(transcript)
        self.assertEqual(len(minutes.decisions), 1)
        self.assertEqual(len(minutes.action_items), 1)
        self.assertEqual(minutes.action_items[0].owner, "鈴木")
        self.assertIn("来週中", minutes.action_items[0].due_date)
        self.assertEqual(len(minutes.open_questions), 1)
        self.assertEqual(len(minutes.risks), 1)
        self.assertTrue(minutes.action_items[0].evidence_segment_ids)


if __name__ == "__main__":
    unittest.main()
