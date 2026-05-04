import unittest

from meeting_agent.core.transcript import format_timestamp, parse_plain_text_transcript, parse_timestamp_to_ms


class TranscriptParsingTest(unittest.TestCase):
    def test_timestamp_parse_and_format(self):
        self.assertEqual(parse_timestamp_to_ms("00:01:02"), 62_000)
        self.assertEqual(parse_timestamp_to_ms("01:02"), 62_000)
        self.assertEqual(format_timestamp(62_000), "00:01:02")

    def test_plain_text_parse(self):
        text = "[00:00:01] 佐藤: 決定します。\n[00:00:12] 田中: 鈴木さん、来週中に調査お願いします。"
        transcript = parse_plain_text_transcript(text, meeting_id="m1", title="t")
        self.assertEqual(len(transcript.segments), 2)
        self.assertEqual(transcript.segments[0].speaker_name, "佐藤")
        self.assertIn("決定", transcript.segments[0].text)
        self.assertEqual(transcript.segments[1].start_ms, 12_000)


if __name__ == "__main__":
    unittest.main()
