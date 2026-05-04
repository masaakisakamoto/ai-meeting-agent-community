# Desktop Alpha Architecture

Community v0.6 introduces a packaged Desktop Alpha path:

```text
Electron/Tauri shell
  -> local Python Desktop Bridge on 127.0.0.1
  -> Desktop Lite UI
  -> simulated recording / diagnostics / sidecar ASR
  -> evidence-linked minutes
```

## Public Community scope

Included:

- Static Desktop Lite UI
- Local Desktop Bridge
- Simulated recording workflow
- WAV diagnostics and level-meter frames
- Sidecar ASR smoke workflow
- Evidence-linked minutes export
- Electron shell skeleton

Excluded private core:

- Production model router
- Advanced Japanese quality engine
- Private evaluation datasets
- Speaker-name mapping
- Enterprise billing, SSO, admin, and audit modules

## Recommended preview flow

```bash
PYTHONPATH=src python -m meeting_agent desktop-alpha-bundle --out-dir demo_out/desktop_alpha_bundle
PYTHONPATH=src python -m meeting_agent desktop-smoke --workspace demo_out/desktop_alpha_bundle
PYTHONPATH=src python -m meeting_agent desktop-package-check --root .
PYTHONPATH=src python -m meeting_agent desktop-serve --workspace demo_out/desktop_alpha_bundle
```

Then open the displayed local URL.
