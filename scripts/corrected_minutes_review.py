from __future__ import annotations

import argparse
from pathlib import Path

from meeting_agent.workflows.corrected_minutes_review import write_review


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare original and corrected ASR minutes outputs."
    )
    parser.add_argument("--original-dir", required=True)
    parser.add_argument("--corrected-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--title", default="Corrected ASR minutes review")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    write_review(
        original_dir=Path(args.original_dir),
        corrected_dir=Path(args.corrected_dir),
        out_dir=Path(args.out_dir),
        title=args.title,
    )
    print(f"Wrote: {Path(args.out_dir) / 'review.md'}")
    print(f"Wrote: {Path(args.out_dir) / 'review.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
