from __future__ import annotations

import json
from pathlib import Path

from meeting_agent.cli import main


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_corrected_minutes_review_cli(tmp_path: Path) -> None:
    original = tmp_path / "original"
    corrected = tmp_path / "corrected"
    out = tmp_path / "review"

    original.mkdir()
    corrected.mkdir()

    write_json(
        original / "asr_minutes_report.json",
        {
            "status": "pass",
            "score": 0.91,
            "quality_status": "pass",
            "quality_score": 0.88,
            "verification_status": "pass",
            "asr_cer": 0.2,
            "asr_wer": 0.5,
        },
    )
    write_json(
        corrected / "asr_minutes_report.json",
        {
            "status": "pass",
            "score": 0.95,
            "quality_status": "pass",
            "quality_score": 0.9,
            "verification_status": "pass",
            "asr_cer": 0.1,
            "asr_wer": 0.4,
        },
    )

    write_json(
        original / "minutes.json",
        {
            "decisions": [{"text": "original decision"}],
            "action_items": [],
            "open_questions": [],
            "risks": [],
        },
    )
    write_json(
        corrected / "minutes.json",
        {
            "decisions": [{"text": "corrected decision"}],
            "action_items": [{"text": "follow up"}],
            "open_questions": [],
            "risks": [],
        },
    )

    (original / "minutes.md").write_text("# Minutes\n\nOriginal term\n", encoding="utf-8")
    (corrected / "minutes.md").write_text("# Minutes\n\nCorrected term\n", encoding="utf-8")

    write_json(
        corrected / "post_correction" / "metrics.json",
        {
            "normalized_ja_cer_before": 0.3,
            "normalized_ja_cer_after": 0.2,
            "absolute_improvement": 0.1,
            "relative_improvement": 0.3333,
            "private_core_included": False,
            "applied_replacements": [
                {"variant": "Original term", "canonical": "Corrected term"}
            ],
        },
    )
    (corrected / "post_correction" / "hypothesis.corrected.txt").write_text(
        "Corrected transcript",
        encoding="utf-8",
    )

    rc = main(
        [
            "corrected-minutes-review",
            "--original-dir",
            str(original),
            "--corrected-dir",
            str(corrected),
            "--out-dir",
            str(out),
            "--title",
            "CLI review smoke",
        ]
    )

    assert rc == 0
    assert (out / "review.md").exists()
    assert (out / "review.json").exists()

    review_md = (out / "review.md").read_text(encoding="utf-8")
    assert "CLI review smoke" in review_md
    assert "ASR post-correction metrics" in review_md
    assert "Human quality review checklist" in review_md

    payload = json.loads((out / "review.json").read_text(encoding="utf-8"))
    assert payload["title"] == "CLI review smoke"
    assert payload["corrected_counts"]["action_items"] == 1
