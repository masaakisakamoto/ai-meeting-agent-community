from __future__ import annotations

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


def load_correction_glossary(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def apply_correction_glossary(text: str, glossary: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    replacements: list[tuple[str, str]] = []

    for entry in glossary.get("entries", []):
        canonical = entry.get("canonical", "")
        for variant in entry.get("variants", []):
            if variant and canonical and variant != canonical:
                replacements.append((variant, canonical))

    replacements.sort(key=lambda pair: len(pair[0]), reverse=True)

    corrected = text
    applied: list[dict[str, str]] = []

    for variant, canonical in replacements:
        if variant in corrected:
            corrected = corrected.replace(variant, canonical)
            applied.append({"from": variant, "to": canonical})

    return corrected, applied


def transcript_text_from_payload(payload: Any) -> str:
    texts: list[str] = []

    def visit(value: Any, key: str | None = None) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                visit(v, k)
        elif isinstance(value, list):
            for item in value:
                visit(item, key)
        elif isinstance(value, str) and key == "text":
            texts.append(value)

    visit(payload)
    return "\n".join(texts)


def correct_transcript_payload(payload: Any, glossary: dict[str, Any]) -> tuple[Any, list[dict[str, str]]]:
    applied: list[dict[str, str]] = []

    def visit(value: Any, key: str | None = None) -> Any:
        if isinstance(value, dict):
            return {k: visit(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [visit(item, key) for item in value]
        if isinstance(value, str) and key in {"text", "content"}:
            corrected, replacements = apply_correction_glossary(value, glossary)
            applied.extend(replacements)
            return corrected
        return value

    return visit(payload), applied


def evaluate_correction(
    *,
    reference_text: str,
    original_text: str,
    corrected_text: str,
    applied_replacements: list[dict[str, str]],
    glossary_path: str | Path | None = None,
    use_corrected_transcript: bool = False,
) -> dict[str, Any]:
    ref_norm = normalize_ja(reference_text)
    original_norm = normalize_ja(original_text)
    corrected_norm = normalize_ja(corrected_text)

    before = round(cer(ref_norm, original_norm), 4)
    after = round(cer(ref_norm, corrected_norm), 4)

    return {
        "glossary": str(glossary_path) if glossary_path else None,
        "use_corrected_transcript": bool(use_corrected_transcript),
        "normalized_ja_cer_before": before,
        "normalized_ja_cer_after": after,
        "absolute_improvement": round(before - after, 4),
        "relative_improvement": round((before - after) / before, 4) if before else 0.0,
        "applied_replacements": applied_replacements,
        "reference_chars_normalized": len(ref_norm),
        "hypothesis_chars_normalized": len(original_norm),
        "corrected_chars_normalized": len(corrected_norm),
        "private_core_included": False,
    }
