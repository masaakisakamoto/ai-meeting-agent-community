import unittest

from meeting_agent.evals.metrics import cer, evaluate_text, wer
from meeting_agent.security.redaction import redact_text


class SecurityAndMetricsTest(unittest.TestCase):
    def test_redaction(self):
        redacted, report = redact_text("連絡先は test@example.com と 090-1234-5678 です。")
        self.assertIn("[REDACTED_EMAIL]", redacted)
        self.assertIn("[REDACTED_PHONE]", redacted)
        self.assertEqual(report.replacements["email"], 1)
        self.assertEqual(report.replacements["phone"], 1)

    def test_metrics(self):
        self.assertEqual(cer("abc", "abc"), 0)
        self.assertEqual(wer("hello world", "hello world"), 0)
        result = evaluate_text("hello world", "hello")
        self.assertGreater(result.wer, 0)


if __name__ == "__main__":
    unittest.main()
