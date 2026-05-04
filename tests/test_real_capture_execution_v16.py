from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from meeting_agent.audio import run_microphone_alpha_recording
from meeting_agent.desktop.bridge import BridgeConfig, handle_bridge_request
from meeting_agent.workflows.real_capture_execution import (
    build_real_capture_execution_pack,
    evaluate_real_capture_execution,
    write_real_capture_execution_gate_report,
    write_real_capture_execution_pack_report,
)


class RealCaptureExecutionV16Tests(unittest.TestCase):
    def test_execution_pack_is_safe_and_writes_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pack"
            report = build_real_capture_execution_pack(out_dir=out, duration_ms=3000)
            self.assertEqual(report.status, "pass")
            self.assertFalse(report.opens_microphone)
            self.assertFalse(report.private_core_included)
            self.assertTrue((out / "scripts" / "02_live_capture.sh").exists())
            self.assertIn("--live", report.commands["02_live_capture"])
            self.assertIn("--participants-notified", report.commands["02_live_capture"])

    def test_execution_gate_warns_without_live_capture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mic = Path(tmp) / "mic"
            run_microphone_alpha_recording(out_dir=mic, dry_run=True)
            report = evaluate_real_capture_execution(mic_dir=mic, require_live_artifacts=True)
            self.assertIn(report.status, {"warn", "fail"})
            self.assertFalse(report.private_core_included)
            check_ids = {check.id for check in report.checks}
            self.assertIn("recording_safety_gate", check_ids)
            self.assertIn("audit_live_sequence", check_ids)

    def test_execution_report_writers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = build_real_capture_execution_pack(out_dir=root / "pack")
            write_real_capture_execution_pack_report(pack, out_json=root / "pack.json", out_md=root / "pack.md")
            self.assertTrue((root / "pack.json").exists())
            mic = root / "mic"
            run_microphone_alpha_recording(out_dir=mic, dry_run=True)
            gate = evaluate_real_capture_execution(mic_dir=mic, require_live_artifacts=False)
            write_real_capture_execution_gate_report(gate, out_json=root / "gate.json", out_md=root / "gate.md")
            self.assertTrue((root / "gate.md").exists())

    def test_bridge_real_capture_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_microphone_alpha_recording(out_dir=workspace / "microphone_alpha", dry_run=True)
            config = BridgeConfig(workspace=workspace)
            status, pack = handle_bridge_request("GET", "/api/real-capture/execution-pack", {}, config=config)
            self.assertEqual(status, 200)
            self.assertEqual(pack["status"], "ok")
            self.assertFalse(pack["private_core_included"])
            status, gate = handle_bridge_request("GET", "/api/real-capture/execution-gate?allow_dry_run=1", {}, config=config)
            self.assertEqual(status, 200)
            self.assertIn(gate["status"], {"ok", "fail"})
            self.assertFalse(gate["private_core_included"])


if __name__ == "__main__":
    unittest.main()
