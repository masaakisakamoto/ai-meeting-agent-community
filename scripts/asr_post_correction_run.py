from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def apply_glossary(text: str, glossary: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
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


def run_command(cmd: list[str], log_path: Path) -> tuple[int, float]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src" + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=Path.cwd(),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    elapsed_s = round(time.time() - started, 3)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(proc.stdout, encoding="utf-8")

    return proc.returncode, elapsed_s


def run_asr_to_minutes(
    audio_path: Path,
    reference: Path,
    out_dir: Path,
    model_size: str,
    device: str,
) -> tuple[int, float]:
    cmd = [
        sys.executable,
        "-m",
        "meeting_agent",
        "asr-to-minutes",
        "--audio-path",
        str(audio_path),
        "--provider",
        "faster-whisper",
        "--model-size",
        model_size,
        "--device",
        device,
        "--reference",
        str(reference),
        "--out-dir",
        str(out_dir),
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "asr_post_correction_command.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")
    return run_command(cmd, out_dir / "asr_post_correction_asr_run.log")


def generate_corrected_minutes(
    audio_path: Path,
    corrected_transcript: str,
    out_dir: Path,
) -> tuple[int, float, Path]:
    post_dir = out_dir / "post_correction"
    corrected_mic_dir = post_dir / "corrected_mic"
    corrected_minutes_dir = post_dir / "corrected_minutes"

    if corrected_mic_dir.exists():
        shutil.rmtree(corrected_mic_dir)
    if corrected_minutes_dir.exists():
        shutil.rmtree(corrected_minutes_dir)

    corrected_mic_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(audio_path, corrected_mic_dir / "audio.wav")
    (corrected_mic_dir / "audio.transcript.txt").write_text(corrected_transcript, encoding="utf-8")

    cmd = [
        sys.executable,
        "-m",
        "meeting_agent",
        "microphone-to-minutes",
        "--mic-dir",
        str(corrected_mic_dir),
        "--out-dir",
        str(corrected_minutes_dir),
        "--provider",
        "sidecar",
    ]

    (post_dir / "corrected_minutes_command.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")
    returncode, elapsed_s = run_command(cmd, post_dir / "corrected_minutes_run.log")
    return returncode, elapsed_s, corrected_minutes_dir


def write_metrics(
    out_dir: Path,
    reference_path: Path,
    hypothesis_path: Path,
    glossary_path: Path,
    original: str,
    corrected: str,
    applied: list[dict[str, str]],
    asr_returncode: int,
    asr_elapsed_s: float,
    corrected_minutes_returncode: int | None,
    corrected_minutes_elapsed_s: float | None,
    corrected_minutes_dir: Path | None,
) -> dict[str, Any]:
    post_dir = out_dir / "post_correction"
    post_dir.mkdir(parents=True, exist_ok=True)

    reference = reference_path.read_text(encoding="utf-8", errors="replace")

    ref_norm = normalize_ja(reference)
    original_norm = normalize_ja(original)
    corrected_norm = normalize_ja(corrected)

    before = round(cer(ref_norm, original_norm), 4)
    after = round(cer(ref_norm, corrected_norm), 4)

    metrics = {
        "asr_returncode": asr_returncode,
        "asr_elapsed_s": asr_elapsed_s,
        "corrected_minutes_returncode": corrected_minutes_returncode,
        "corrected_minutes_elapsed_s": corrected_minutes_elapsed_s,
        "corrected_minutes_dir": str(corrected_minutes_dir) if corrected_minutes_dir else None,
        "corrected_minutes_html": str(corrected_minutes_dir / "minutes.html") if corrected_minutes_dir else None,
        "reference": str(reference_path),
        "hypothesis": str(hypothesis_path),
        "glossary": str(glossary_path),
        "normalized_ja_cer_before": before,
        "normalized_ja_cer_after": after,
        "absolute_improvement": round(before - after, 4),
        "relative_improvement": round((before - after) / before, 4) if before else 0.0,
        "applied_replacements": applied,
        "reference_chars_normalized": len(ref_norm),
        "hypothesis_chars_normalized": len(original_norm),
        "corrected_chars_normalized": len(corrected_norm),
        "private_core_included": False,
    }

    (post_dir / "hypothesis.original.txt").write_text(original, encoding="utf-8")
    (post_dir / "hypothesis.corrected.txt").write_text(corrected, encoding="utf-8")
    (post_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# ASR Post-correction Report",
        "",
        f"- ASR return code: `{asr_returncode}`",
        f"- ASR elapsed seconds: `{asr_elapsed_s}`",
        f"- Corrected minutes return code: `{corrected_minutes_returncode}`",
        f"- Corrected minutes elapsed seconds: `{corrected_minutes_elapsed_s}`",
        f"- Corrected minutes HTML: `{metrics['corrected_minutes_html']}`",
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
            lines.append(f"- `{item['from']}` → `{item['to']}`")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Safety",
        "",
        "- Public-safe glossary correction only",
        "- No private Quality Engine code included",
        "- Generated outputs are local artifacts and should not be committed",
        "",
    ])

    (post_dir / "metrics.md").write_text("\n".join(lines), encoding="utf-8")

    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ASR-to-minutes with public-safe post-correction metrics.")
    parser.add_argument("--audio-path", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--glossary", default="configs/asr_correction_glossary_ja.example.json")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--model-size", default="medium")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--generate-corrected-minutes", action="store_true")
    args = parser.parse_args()

    audio_path = Path(args.audio_path)
    reference = Path(args.reference)
    glossary_path = Path(args.glossary)
    out_dir = Path(args.out_dir)

    if not audio_path.exists():
        raise SystemExit(f"audio not found: {audio_path}")
    if not reference.exists():
        raise SystemExit(f"reference not found: {reference}")
    if not glossary_path.exists():
        raise SystemExit(f"glossary not found: {glossary_path}")

    asr_returncode, asr_elapsed_s = run_asr_to_minutes(
        audio_path=audio_path,
        reference=reference,
        out_dir=out_dir,
        model_size=args.model_size,
        device=args.device,
    )

    hypothesis_path = out_dir / "asr_validation" / "hypothesis.txt"
    if not hypothesis_path.exists():
        raise SystemExit(f"hypothesis not found after ASR run: {hypothesis_path}")

    original = hypothesis_path.read_text(encoding="utf-8", errors="replace")
    glossary = load_json(glossary_path)
    corrected, applied = apply_glossary(original, glossary)

    corrected_minutes_returncode = None
    corrected_minutes_elapsed_s = None
    corrected_minutes_dir = None

    if args.generate_corrected_minutes:
        corrected_minutes_returncode, corrected_minutes_elapsed_s, corrected_minutes_dir = generate_corrected_minutes(
            audio_path=audio_path,
            corrected_transcript=corrected,
            out_dir=out_dir,
        )

    metrics = write_metrics(
        out_dir=out_dir,
        reference_path=reference,
        hypothesis_path=hypothesis_path,
        glossary_path=glossary_path,
        original=original,
        corrected=corrected,
        applied=applied,
        asr_returncode=asr_returncode,
        asr_elapsed_s=asr_elapsed_s,
        corrected_minutes_returncode=corrected_minutes_returncode,
        corrected_minutes_elapsed_s=corrected_minutes_elapsed_s,
        corrected_minutes_dir=corrected_minutes_dir,
    )

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"Wrote: {out_dir / 'post_correction' / 'metrics.md'}")
    return 0 if asr_returncode == 0 and (corrected_minutes_returncode in (None, 0)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
