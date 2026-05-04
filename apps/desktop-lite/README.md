# Desktop Lite / Desktop Alpha Preview

This directory documents the dependency-free UI shipped in `meeting_agent.ui.assets`.

Generate a runnable static bundle from a transcript:

```bash
PYTHONPATH=src python -m meeting_agent demo --out-dir ./demo_out
open ./demo_out/desktop_lite/index.html
```

Create a local Desktop Alpha workspace and smoke-test it:

```bash
PYTHONPATH=src python -m meeting_agent desktop-alpha \
  --workspace ./desktop_alpha_out \
  --out-json ./desktop_alpha_out/desktop_alpha_report.json \
  --out-md ./desktop_alpha_out/desktop_alpha_report.md
```

Serve the bundle with local bridge APIs:

```bash
PYTHONPATH=src python -m meeting_agent desktop-serve \
  --workspace ./desktop_alpha_out \
  --ui-dir ./desktop_alpha_out/desktop_lite \
  --open-browser
```

The static bundle works without a backend. When served through `desktop-serve`,
the UI can call local Community Bridge APIs for health checks, simulated
recording, and deterministic smoke workflows.

The bridge intentionally binds to `127.0.0.1` and does not include private
quality-engine code, production model routing, private evaluation data, or
enterprise modules.
