from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import socket
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent.core.schemas import utc_now_iso

RECOMMENDED_PYTHON = "3.12"
DEFAULT_BRIDGE_PORT = 8765


@dataclass(frozen=True)
class DevEnvironmentCheck:
    id: str
    status: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DevEnvironmentReport:
    status: str
    score: float
    generated_at: str
    platform: str
    python_version: str
    executable: str
    cwd: str
    recommended_python: str
    bridge_port: int
    checks: list[DevEnvironmentCheck]
    recommendations: list[str]
    private_core_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Developer Environment Doctor",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score}`",
            f"- Platform: `{self.platform}`",
            f"- Python: `{self.python_version}`",
            f"- Executable: `{self.executable}`",
            f"- Recommended Python: `{self.recommended_python}`",
            f"- Bridge port: `{self.bridge_port}`",
            f"- Private core included: `{str(self.private_core_included).lower()}`",
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "|---|---|---|",
        ]
        for check in self.checks:
            lines.append(f"| {check.id} | `{check.status}` | {_md(check.detail)} |")
        lines.extend(["", "## Recommendations", ""])
        for item in self.recommendations:
            lines.append(f"- {item}")
        lines.append("")
        return "\n".join(lines)


def run_dev_environment_doctor(*, root: str | Path = ".", bridge_port: int = DEFAULT_BRIDGE_PORT) -> DevEnvironmentReport:
    root = Path(root)
    checks: list[DevEnvironmentCheck] = []
    py = sys.version_info
    py_str = f"{py.major}.{py.minor}.{py.micro}"
    supported = (py.major, py.minor) >= (3, 10)
    py_status = "pass" if supported else "fail"
    py_detail = "Supported Python runtime for Community core."
    if supported and (py.major, py.minor) != (3, 12):
        py_status = "warn"
        py_detail = "Community core can run, but Python 3.12 is recommended for optional audio/ASR dependencies."
    checks.append(DevEnvironmentCheck("python_runtime", py_status, py_detail, {"version": py_str}))
    checks.append(DevEnvironmentCheck("project_root", "pass" if (root / "pyproject.toml").exists() else "fail", "pyproject.toml found." if (root / "pyproject.toml").exists() else "Run from the project root or pass --root.", {"root": str(root)}))
    checks.append(_module_check("sounddevice", "Optional real microphone capture dependency."))
    checks.append(_module_check("numpy", "Optional numerical dependency required by sounddevice capture."))
    checks.append(_module_check("faster_whisper", "Optional local ASR dependency."))
    checks.append(_tool_check("ffmpeg", "Recommended for future audio conversion workflows."))
    checks.append(_tool_check("brew", "Useful on macOS for installing Python 3.12 and PortAudio."))
    checks.append(_port_check(bridge_port))
    checks.append(DevEnvironmentCheck("publication_hold", "pass", "Publication gate should remain on hold during private alpha."))
    checks.append(DevEnvironmentCheck("private_core_excluded", "pass", "Private Quality Engine is not included in Community source."))
    status = _status(checks)
    return DevEnvironmentReport(
        status=status,
        score=_score(checks),
        generated_at=utc_now_iso(),
        platform=platform.platform(),
        python_version=py_str,
        executable=sys.executable,
        cwd=os.getcwd(),
        recommended_python=RECOMMENDED_PYTHON,
        bridge_port=bridge_port,
        checks=checks,
        recommendations=_recommendations(checks, py),
        private_core_included=False,
    )


def write_dev_environment_report(report: DevEnvironmentReport, *, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def _module_check(name: str, detail: str) -> DevEnvironmentCheck:
    available = importlib.util.find_spec(name) is not None
    return DevEnvironmentCheck(f"python_module_{name}", "pass" if available else "warn", f"{name} is installed. {detail}" if available else f"{name} is not installed. {detail}", {"module": name, "available": available})


def _tool_check(name: str, detail: str) -> DevEnvironmentCheck:
    path = shutil.which(name)
    return DevEnvironmentCheck(f"tool_{name}", "pass" if path else "warn", f"{name} found at {path}." if path else f"{name} not found. {detail}", {"tool": name, "path": path})


def _port_check(port: int) -> DevEnvironmentCheck:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)
    try:
        result = sock.connect_ex(("127.0.0.1", port))
    finally:
        sock.close()
    if result == 0:
        return DevEnvironmentCheck("bridge_port_available", "warn", f"Port {port} is already in use. This may be an existing Desktop Bridge.", {"port": port, "in_use": True})
    return DevEnvironmentCheck("bridge_port_available", "pass", f"Port {port} appears available for Desktop Bridge.", {"port": port, "in_use": False})


def _status(checks: list[DevEnvironmentCheck]) -> str:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "pass"


def _score(checks: list[DevEnvironmentCheck]) -> float:
    score = 1.0
    for check in checks:
        if check.status == "warn":
            score -= 0.055
        elif check.status == "fail":
            score -= 0.22
    return round(max(0.0, score), 3)


def _recommendations(checks: list[DevEnvironmentCheck], py) -> list[str]:
    by_id = {check.id: check for check in checks}
    recs: list[str] = []
    if (py.major, py.minor) != (3, 12):
        recs.append("For real microphone and local ASR validation, create a Python 3.12 virtual environment before installing optional audio dependencies.")
    if by_id.get("python_module_sounddevice") and by_id["python_module_sounddevice"].status != "pass":
        recs.append("Install optional audio support with `python -m pip install -e \".[audio]\"` inside the Python 3.12 virtual environment.")
    if by_id.get("python_module_faster_whisper") and by_id["python_module_faster_whisper"].status != "pass":
        recs.append("Keep faster-whisper optional until microphone capture is stable; use sidecar ASR for deterministic private-alpha demos.")
    if by_id.get("bridge_port_available") and by_id["bridge_port_available"].status == "warn":
        recs.append("If the bridge UI behaves unexpectedly, stop the existing bridge with `kill -15 $(lsof -tiTCP:8765 -sTCP:LISTEN)` and restart it.")
    recs.append("Keep `publication-gate` on hold until public alpha criteria are intentionally satisfied.")
    return recs


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
