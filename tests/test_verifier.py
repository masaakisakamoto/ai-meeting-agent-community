import unittest

from meeting_agent.core.schemas import Decision, MinutesDraft
from meeting_agent.core.transcript import parse_plain_text_transcript
from meeting_agent.intelligence.rule_minutes import RuleBasedMinutesGenerator
from meeting_agent.intelligence.verifier import MinutesVerifier


class VerifierTest(unittest.TestCase):
    def test_verifier_passes_grounded_minutes(self):
        transcript = parse_plain_text_transcript(
            "[00:00:01] 佐藤: v0.1はMarkdown出力で進めることで決定します。",
            meeting_id="m1",
            title="demo",
        )
        minutes = RuleBasedMinutesGenerator().generate(transcript)
        report = MinutesVerifier().verify(transcript, minutes)
        self.assertEqual(report.status, "pass")
        self.assertGreaterEqual(report.score, 0.8)

    def test_verifier_flags_missing_evidence(self):
        transcript = parse_plain_text_transcript("[00:00:01] 佐藤: こんにちは。", meeting_id="m1", title="demo")
        minutes = MinutesDraft(
            meeting_id="m1",
            title="demo",
            decisions=[Decision(id="dec_bad", text="存在しない決定", confidence=0.5, evidence_segment_ids=[])],
        )
        report = MinutesVerifier().verify(transcript, minutes)
        self.assertEqual(report.status, "needs_review")
        self.assertTrue(report.issues)


if __name__ == "__main__":
    unittest.main()
