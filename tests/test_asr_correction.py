from __future__ import annotations

import unittest

from meeting_agent.workflows.asr_correction import (
    apply_correction_glossary,
    correct_transcript_payload,
    evaluate_correction,
    transcript_text_from_payload,
)


class ASRCorrectionTests(unittest.TestCase):
    def test_apply_correction_glossary_replaces_public_alpha_variant(self) -> None:
        glossary = {
            "entries": [
                {
                    "canonical": "Public Alpha",
                    "variants": ["パブリックアルファ"],
                }
            ]
        }

        corrected, applied = apply_correction_glossary(
            "今日はパブリックアルファの確認です。",
            glossary,
        )

        self.assertIn("Public Alpha", corrected)
        self.assertEqual(applied, [{"from": "パブリックアルファ", "to": "Public Alpha"}])

    def test_correct_transcript_payload_only_changes_text_content(self) -> None:
        glossary = {
            "entries": [
                {
                    "canonical": "Public Alpha",
                    "variants": ["パブリックアルファ"],
                }
            ]
        }
        payload = {
            "meeting_id": "mtg_test",
            "segments": [
                {
                    "speaker": "話者",
                    "text": "パブリックアルファを確認します。",
                    "metadata": {
                        "note": "パブリックアルファ"
                    },
                }
            ],
        }

        corrected, applied = correct_transcript_payload(payload, glossary)

        self.assertIn("Public Alpha", corrected["segments"][0]["text"])
        self.assertEqual(corrected["segments"][0]["metadata"]["note"], "パブリックアルファ")
        self.assertEqual(applied, [{"from": "パブリックアルファ", "to": "Public Alpha"}])

    def test_evaluate_correction_reports_improvement(self) -> None:
        metrics = evaluate_correction(
            reference_text="話者: Public Alphaを確認します。",
            original_text="話者: パブリックアルファを確認します。",
            corrected_text="話者: Public Alphaを確認します。",
            applied_replacements=[{"from": "パブリックアルファ", "to": "Public Alpha"}],
            glossary_path="glossary.json",
            use_corrected_transcript=True,
        )

        self.assertGreater(metrics["normalized_ja_cer_before"], metrics["normalized_ja_cer_after"])
        self.assertFalse(metrics["private_core_included"])

    def test_transcript_text_from_payload_collects_text_fields(self) -> None:
        payload = {
            "segments": [
                {"text": "一つ目"},
                {"text": "二つ目"},
            ]
        }

        self.assertEqual(transcript_text_from_payload(payload), "一つ目\n二つ目")


if __name__ == "__main__":
    unittest.main()
