from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
from typing import Any


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def count_list(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    return len(value) if isinstance(value, list) else 0


def minutes_counts(minutes_json: Path) -> dict[str, int]:
    data = read_json(minutes_json)
    return {
        "decisions": count_list(data, "decisions"),
        "action_items": count_list(data, "action_items"),
        "open_questions": count_list(data, "open_questions"),
        "risks": count_list(data, "risks"),
    }


def report_summary(report_json: Path) -> dict[str, Any]:
    data = read_json(report_json)
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    return {
        "status": data.get("status"),
        "score": data.get("score"),
        "quality_score": summary.get("quality_score"),
        "quality_status": summary.get("quality_status"),
        "verification_status": summary.get("verification_status"),
        "asr_cer": summary.get("asr_cer", metrics.get("cer")),
        "asr_wer": summary.get("asr_wer", metrics.get("wer")),
        "private_core_included": data.get("private_core_included", summary.get("private_core_included")),
    }


def make_diff(original: str, corrected: str, max_lines: int = 180) -> list[str]:
    diff = list(
        difflib.unified_diff(
            original.splitlines(),
            corrected.splitlines(),
            fromfile="original_minutes.md",
            tofile="corrected_minutes.md",
            lineterm="",
            n=3,
        )
    )
    if len(diff) > max_lines:
        return diff[:max_lines] + ["... diff truncated ..."]
    return diff


def write_review(
    *,
    original_dir: Path,
    corrected_dir: Path,
    out_dir: Path,
    title: str,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    original_report = report_summary(original_dir / "asr_minutes_report.json")
    corrected_report = report_summary(corrected_dir / "asr_minutes_report.json")

    original_counts = minutes_counts(original_dir / "minutes.json")
    corrected_counts = minutes_counts(corrected_dir / "minutes.json")

    correction_metrics = read_json(corrected_dir / "post_correction" / "metrics.json")

    original_hypothesis = read_text(original_dir / "asr_validation" / "hypothesis.txt")
    corrected_hypothesis = read_text(corrected_dir / "post_correction" / "hypothesis.corrected.txt")

    original_minutes_md = read_text(original_dir / "minutes.md")
    corrected_minutes_md = read_text(corrected_dir / "minutes.md")

    diff_lines = make_diff(original_minutes_md, corrected_minutes_md)

    payload = {
        "title": title,
        "original_dir": str(original_dir),
        "corrected_dir": str(corrected_dir),
        "original_report": original_report,
        "corrected_report": corrected_report,
        "original_counts": original_counts,
        "corrected_counts": corrected_counts,
        "correction_metrics": correction_metrics,
        "private_core_included": False,
    }

    (out_dir / "review.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines: list[str] = [
        f"# {title}",
        "",
        "## Summary",
        "",
        "| Item | Original | Corrected |",
        "|---|---:|---:|",
        f"| Status | `{original_report.get('status')}` | `{corrected_report.get('status')}` |",
        f"| Score | `{original_report.get('score')}` | `{corrected_report.get('score')}` |",
        f"| Quality status | `{original_report.get('quality_status')}` | `{corrected_report.get('quality_status')}` |",
        f"| Quality score | `{original_report.get('quality_score')}` | `{corrected_report.get('quality_score')}` |",
        f"| Verification status | `{original_report.get('verification_status')}` | `{corrected_report.get('verification_status')}` |",
        f"| ASR CER | `{original_report.get('asr_cer')}` | `{corrected_report.get('asr_cer')}` |",
        f"| ASR WER | `{original_report.get('asr_wer')}` | `{corrected_report.get('asr_wer')}` |",
        f"| Decisions | `{original_counts['decisions']}` | `{corrected_counts['decisions']}` |",
        f"| Action items | `{original_counts['action_items']}` | `{corrected_counts['action_items']}` |",
        f"| Open questions | `{original_counts['open_questions']}` | `{corrected_counts['open_questions']}` |",
        f"| Risks | `{original_counts['risks']}` | `{corrected_counts['risks']}` |",
        "",
        "## ASR post-correction metrics",
        "",
        f"- Normalized JA CER before: `{correction_metrics.get('normalized_ja_cer_before')}`",
        f"- Normalized JA CER after: `{correction_metrics.get('normalized_ja_cer_after')}`",
        f"- Absolute improvement: `{correction_metrics.get('absolute_improvement')}`",
        f"- Relative improvement: `{correction_metrics.get('relative_improvement')}`",
        f"- Private core included: `{correction_metrics.get('private_core_included')}`",
        "",
        "## Applied replacements",
        "",
    ]

    applied = correction_metrics.get("applied_replacements") or []
    if applied:
        for item in applied:
            lines.append(f"- `{item.get('from')}` -> `{item.get('to')}`")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Original hypothesis",
            "",
            original_hypothesis.strip() or "(missing)",
            "",
            "## Corrected hypothesis",
            "",
            corrected_hypothesis.strip() or "(missing)",
            "",
            "## Minutes diff",
            "",
        ]
    )

    if diff_lines:
        lines.extend(diff_lines)
    else:
        lines.append("No minutes.md diff detected.")

    lines.extend(
        [
            "",
            "## Human quality review checklist",
            "",
            "- [ ] Corrected transcript is closer to the intended Japanese meaning.",
            "- [ ] Domain terms are corrected safely.",
            "- [ ] No hallucinated decisions are introduced.",
            "- [ ] Action items remain accurate.",
            "- [ ] Evidence links remain usable.",
            "- [ ] Quality gate remains pass.",
            "- [ ] Private Quality Engine remains excluded.",
            "- [ ] Raw audio and generated outputs remain untracked.",
            "",
            "## Decision",
            "",
            "This report is a local review artifact. Do not commit generated review outputs.",
            "",
        ]
    )

    (out_dir / "review.md").write_text("\n".join(lines), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare original and corrected ASR minutes outputs.")
    parser.add_argument("--original-dir", required=True)
    parser.add_argument("--corrected-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--title", default="Corrected Minutes Quality Review")
    args = parser.parse_args()

    original_dir = Path(args.original_dir)
    corrected_dir = Path(args.corrected_dir)
    out_dir = Path(args.out_dir)

    if not original_dir.exists():
        raise SystemExit(f"original dir not found: {original_dir}")
    if not corrected_dir.exists():
        raise SystemExit(f"corrected dir not found: {corrected_dir}")

    payload = write_review(
        original_dir=original_dir,
        corrected_dir=corrected_dir,
        out_dir=out_dir,
        title=args.title,
    )

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Wrote: {out_dir / 'review.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
