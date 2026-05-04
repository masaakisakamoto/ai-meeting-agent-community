from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from meeting_agent.audio.live_guard import LIVE_CONFIRMATION_PHRASE, evaluate_recording_safety_gate
from meeting_agent.core.schemas import utc_now_iso


@dataclass(frozen=True)
class LiveCapturePlan:
    status: str
    generated_at: str
    out_dir: str
    duration_ms: int
    device_id: str
    sample_rate_hz: int
    channels: int
    confirmation_phrase: str
    dry_run_command: list[str]
    live_command: list[str]
    safety_gate: dict[str, Any]
    next_steps: list[str]
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        return "\n".join([
            "# Live Capture Plan",
            "",
            f"- Status: `{self.status}`",
            f"- Output directory: `{self.out_dir}`",
            f"- Duration: `{self.duration_ms} ms`",
            f"- Device: `{self.device_id}`",
            f"- Sample rate: `{self.sample_rate_hz}`",
            f"- Channels: `{self.channels}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            "",
            "## Dry-run command",
            "",
            "```bash",
            " ".join(self.dry_run_command),
            "```",
            "",
            "## Live command",
            "",
            "```bash",
            " ".join(self.live_command),
            "```",
            "",
            "## Required confirmation phrase",
            "",
            f"`{self.confirmation_phrase}`",
            "",
            "## Next steps",
            "",
            *[f"- {step}" for step in self.next_steps],
            "",
        ])


def build_live_capture_plan(*, out_dir: str | Path = "mic_alpha_live", duration_ms: int = 3000, device_id: str = "microphone:default", sample_rate_hz: int = 16000, channels: int = 1) -> LiveCapturePlan:
    out_dir = str(out_dir)
    safety_gate = evaluate_recording_safety_gate(live_requested=False, duration_ms=duration_ms, publication_hold=True)
    base = ["PYTHONPATH=src", "python", "-m", "meeting_agent", "record-microphone-alpha", "--out-dir", out_dir, "--duration-ms", str(duration_ms), "--device-id", device_id, "--sample-rate", str(sample_rate_hz), "--channels", str(channels)]
    live = base + ["--live", "--confirmation", LIVE_CONFIRMATION_PHRASE, "--notice-acknowledged", "--participants-notified"]
    return LiveCapturePlan(
        status="ready_for_dry_run",
        generated_at=utc_now_iso(),
        out_dir=out_dir,
        duration_ms=duration_ms,
        device_id=device_id,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        confirmation_phrase=LIVE_CONFIRMATION_PHRASE,
        dry_run_command=base,
        live_command=live,
        safety_gate=safety_gate.to_dict(),
        next_steps=[
            "Create and activate a Python 3.12 virtual environment.",
            "Install optional audio dependencies with `python -m pip install -e \".[audio]\"`.",
            "Run microphone-doctor and list-audio-devices before live capture.",
            "Keep publication-gate on hold while validating real audio privately.",
        ],
        private_core_included=False,
    )


def write_live_capture_plan(plan: LiveCapturePlan, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(plan.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(plan.to_markdown(), encoding="utf-8")
