from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


def normalize_ja(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = re.sub(r"\d{2}:\d{2}:\d{2}(?:\.\d+)?", "", text)
    text = re.sub(r"\d{2}:\d{2}(?:\.\d+)?", "", text)
    text = re.sub(r"\bunknown\s*:", "", text, flags=re.I)
    text = text.replace("話者:", "")
    text = re.sub(r"[\s\t\r\n]+", "", text)
    text = re.sub(r"[、。,.!！?？:：;；「」『』（）()\[\]【】<>《》…・_\-—/\\|\"'`]", "", text)
    return text


def edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            curr.append(
                min(
                    prev[j] + 1,
                    curr[j - 1] + 1,
                    prev[j - 1] + (0 if ca == cb else 1),
                )
            )
        prev = curr
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return edit_distance(reference, hypothesis) / len(reference)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_glossary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def apply_glossary(text: str, glossary: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    replacements: list[tuple[str, str]] = []

    for entry in glossary.get("entries", []):
        canonical = entry.get("canonical", "")
        for variant in entry.get("variants", []):
            if variant and canonical and variant != canonical:
                replacements.append((variant, canonical))

    replacements.sort(key=lambda pair: len(pair[0]), reverse=True)

    applied: list[dict[str, str]] = []
    corrected = text

    for variant, canonical in replacements:
        if variant in corrected:
            corrected = corrected.replace(variant, canonical)
            applied.append({"from": variant, "to": canonical})

    return corrected, applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate public-safe Japanese ASR post-correction.")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--glossary", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    reference_path = Path(args.reference)
    hypothesis_path = Path(args.hypothesis)
    glossary_path = Path(args.glossary)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    reference = read_text(reference_path)
    hypothesis = read_text(hypothesis_path)
    glossary = load_glossary(glossary_path)

    corrected, applied = apply_glossary(hypothesis, glossary)

    ref_norm = normalize_ja(reference)
    hyp_norm = normalize_ja(hypothesis)
    corrected_norm = normalize_ja(corrected)

    before = round(cer(ref_norm, hyp_norm), 4)
    after = round(cer(ref_norm, corrected_norm), 4)

    metrics = {
        "reference": str(reference_path),
        "hypothesis": str(hypothesis_path),
        "glossary": str(glossary_path),
        "normalized_ja_cer_before": before,
        "normalized_ja_cer_after": after,
        "absolute_improvement": round(before - after, 4),
        "relative_improvement": round(((before - after) / before), 4) if before else 0.0,
        "applied_replacements": applied,
        "reference_chars_normalized": len(ref_norm),
        "hypothesis_chars_normalized": len(hyp_norm),
        "corrected_chars_normalized": len(corrected_norm),
    }

    (out_dir / "hypothesis.original.txt").write_text(hypothesis, encoding="utf-8")
    (out_dir / "hypothesis.corrected.txt").write_text(corrected, encoding="utf-8")
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = [
        "# ASR Correction Evaluation",
        "",
        f"- Normalized JA CER before: `{before}`",
        f"- Normalized JA CER after: `{after}`",
        f"- Absolute improvement: `{metrics['absolute_improvement']}`",
        f"- Relative improvement: `{metrics['relative_improvement']}`",
        "",
        "## Applied replacements",
        "",
    ]

    if applied:
        for item in applied:
            md.append(f"- `{item['from']}` → `{item['to']}`")
    else:
        md.append("- None")

    md.extend([
        "",
        "## Note",
        "",
        "This is a public-safe glossary correction evaluation. It is not a production Quality Engine.",
        "",
    ])

    (out_dir / "metrics.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"Wrote: {out_dir / 'metrics.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
