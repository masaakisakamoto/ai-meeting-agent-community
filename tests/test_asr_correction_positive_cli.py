from __future__ import annotations

import json
import wave
from pathlib import Path

from meeting_agent.cli import main


def test_asr_to_minutes_positive_glossary_correction_cli(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    sidecar = tmp_path / "sidecar.txt"
    reference = tmp_path / "reference.txt"
    glossary = tmp_path / "glossary.json"
    out = tmp_path / "corrected_minutes"

    # Sidecar mode reads transcript text from the sidecar file, but the workflow
    # still validates that the audio path points to a parseable WAV artifact.
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(b"\x00\x00" * 1_600)

    sidecar.write_text(
        "\n".join(
            [
                "アクション: パブリックアルファ の補正を確認する。",
                "アクション: パブリックアルファ のレビューを完了する。",
                "アクション: パブリックアルファ の結果を記録する。",
            ]
        ),
        encoding="utf-8",
    )

    reference.write_text(
        "\n".join(
            [
                "アクション: Public Alpha の補正を確認する。",
                "アクション: Public Alpha のレビューを完了する。",
                "アクション: Public Alpha の結果を記録する。",
            ]
        ),
        encoding="utf-8",
    )

    glossary.write_text(
        json.dumps(
            {
                "schema_version": "asr-correction-glossary/v1",
                "entries": [
                    {
                        "canonical": "Public Alpha",
                        "variants": ["パブリックアルファ"],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    rc = main(
        [
            "asr-to-minutes",
            "--provider",
            "sidecar",
            "--audio-path",
            str(audio),
            "--sidecar",
            str(sidecar),
            "--reference",
            str(reference),
            "--correction-glossary",
            str(glossary),
            "--generate-corrected-minutes",
            "--out-dir",
            str(out),
            "--title",
            "Positive glossary correction regression",
        ]
    )

    assert rc == 0

    metrics_path = out / "post_correction" / "metrics.json"
    report_path = out / "asr_minutes_report.json"
    corrected_hypothesis_path = out / "post_correction" / "hypothesis.corrected.txt"
    corrected_transcript_path = out / "post_correction" / "transcript.corrected.json"

    assert metrics_path.exists()
    assert report_path.exists()
    assert corrected_hypothesis_path.exists()
    assert corrected_transcript_path.exists()
    assert (out / "minutes.json").exists()
    assert (out / "minutes.md").exists()

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    corrected_hypothesis = corrected_hypothesis_path.read_text(encoding="utf-8")

    replacements = metrics.get("applied_replacements") or []

    assert len(replacements) == 3
    assert metrics["normalized_ja_cer_after"] < metrics["normalized_ja_cer_before"]
    assert metrics["absolute_improvement"] > 0
    assert metrics["relative_improvement"] > 0
    assert metrics["private_core_included"] is False

    assert report["summary"]["asr_post_correction_enabled"] is True
    assert report["summary"]["asr_corrected_minutes_generated"] is True
    assert report["summary"]["private_core_included"] is False
    assert report["private_core_included"] is False

    assert "Public Alpha" in corrected_hypothesis
    assert "パブリックアルファ" not in corrected_hypothesis
