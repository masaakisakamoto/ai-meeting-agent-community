from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence


@dataclass
class TextEvalResult:
    cer: float
    wer: float
    reference_length_chars: int
    reference_length_words: int


def normalize_for_eval(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def cer(reference: str, hypothesis: str) -> float:
    ref = list(normalize_for_eval(reference).replace(" ", ""))
    hyp = list(normalize_for_eval(hypothesis).replace(" ", ""))
    if not ref:
        return 0.0 if not hyp else 1.0
    return _levenshtein(ref, hyp) / len(ref)


def wer(reference: str, hypothesis: str) -> float:
    ref = normalize_for_eval(reference).split()
    hyp = normalize_for_eval(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return _levenshtein(ref, hyp) / len(ref)


def evaluate_text(reference: str, hypothesis: str) -> TextEvalResult:
    ref_norm = normalize_for_eval(reference)
    return TextEvalResult(
        cer=round(cer(reference, hypothesis), 4),
        wer=round(wer(reference, hypothesis), 4),
        reference_length_chars=len(ref_norm.replace(" ", "")),
        reference_length_words=len(ref_norm.split()),
    )


def _levenshtein(a: Sequence[str], b: Sequence[str]) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (0 if ca == cb else 1)
            current.append(min(insert, delete, replace))
        previous = current
    return previous[-1]
