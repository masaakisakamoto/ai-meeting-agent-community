from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any


def slug_model_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model).strip("_")


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
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def run_model(
    model: str,
    audio_path: Path,
    reference: Path,
    out_root: Path,
    device: str,
    compute_type: str | None,
) -> dict[str, Any]:
    slug = slug_model_name(model)
    out_dir = out_root / slug
    out_dir.mkdir(parents=True, exist_ok=True)

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
        model,
        "--device",
        device,
        "--reference",
        str(reference),
        "--out-dir",
        str(out_dir),
    ]

    if compute_type:
        # Kept for forward compatibility. Current CLI may ignore unsupported compute-type;
        # do not append until the project exposes it.
        pass

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

    (out_dir / "command.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")
    (out_dir / "run.log").write_text(proc.stdout, encoding="utf-8")

    metrics = load_json(out_dir / "asr_validation" / "metrics.json")
    report = load_json(out_dir / "asr_minutes_report.json")

    ref_text = read_text(out_dir / "asr_validation" / "reference.txt")
    hyp_text = read_text(out_dir / "asr_validation" / "hypothesis.txt")

    ref_norm = normalize_ja(ref_text)
    hyp_norm = normalize_ja(hyp_text)

    result = {
        "model": model,
        "status": "pass" if proc.returncode == 0 else "fail",
        "returncode": proc.returncode,
        "elapsed_s": elapsed_s,
        "out_dir": str(out_dir),
        "cer": metrics.get("cer"),
        "wer": metrics.get("wer"),
        "normalized_ja_cer": round(cer(ref_norm, hyp_norm), 4),
        "reference_chars_normalized": len(ref_norm),
        "hypothesis_chars_normalized": len(hyp_norm),
        "segments": (report.get("summary") or {}).get("segments"),
        "decisions": (report.get("summary") or {}).get("decisions"),
        "action_items": (report.get("summary") or {}).get("action_items"),
        "verification_status": (report.get("summary") or {}).get("verification_status"),
        "quality_status": (report.get("summary") or {}).get("quality_status"),
        "quality_score": (report.get("summary") or {}).get("quality_score"),
        "private_core_included": (report.get("summary") or {}).get("private_core_included", report.get("private_core_included")),
    }
    return result


def write_summary(out_root: Path, results: list[dict[str, Any]]) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    summary_json = {
        "generated_at_epoch": time.time(),
        "results": results,
        "best_by_normalized_ja_cer": min(
            [r for r in results if r.get("status") == "pass"],
            key=lambda r: r.get("normalized_ja_cer", 999),
            default=None,
        ),
    }
    (out_root / "summary.json").write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# ASR Accuracy Sweep Summary",
        "",
        "| Model | Status | CER | WER | Normalized JA CER | Segments | Actions | Quality | Seconds |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for r in results:
        lines.append(
            "| {model} | {status} | {cer} | {wer} | {normalized_ja_cer} | {segments} | {action_items} | {quality_score} | {elapsed_s} |".format(
                model=r.get("model"),
                status=r.get("status"),
                cer=r.get("cer"),
                wer=r.get("wer"),
                normalized_ja_cer=r.get("normalized_ja_cer"),
                segments=r.get("segments"),
                action_items=r.get("action_items"),
                quality_score=r.get("quality_score"),
                elapsed_s=r.get("elapsed_s"),
            )
        )

    best = summary_json["best_by_normalized_ja_cer"]
    lines.extend(["", "## Recommendation", ""])
    if best:
        lines.append(f"Best current local model by normalized Japanese CER: `{best['model']}`.")
    else:
        lines.append("No passing model run was found.")

    lines.extend([
        "",
        "Generated outputs are local evaluation artifacts and should not be committed.",
        "",
    ])

    (out_root / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a public-safe ASR accuracy sweep.")
    parser.add_argument("--audio-path", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--out-dir", default="asr_accuracy_runs/latest")
    parser.add_argument("--models", nargs="+", default=["small", "medium", "turbo"])
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default=None)
    args = parser.parse_args()

    audio_path = Path(args.audio_path)
    reference = Path(args.reference)
    out_root = Path(args.out_dir)

    if not audio_path.exists():
        raise SystemExit(f"audio not found: {audio_path}")
    if not reference.exists():
        raise SystemExit(f"reference not found: {reference}")

    results: list[dict[str, Any]] = []
    for model in args.models:
        print(f"== Running model: {model} ==", flush=True)
        result = run_model(
            model=model,
            audio_path=audio_path,
            reference=reference,
            out_root=out_root,
            device=args.device,
            compute_type=args.compute_type,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        results.append(result)

    write_summary(out_root, results)
    print(f"Summary written: {out_root / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
