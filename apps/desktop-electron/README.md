# AI Meeting Agent Desktop Alpha — Electron Shell

This is a lightweight Electron shell for the Community Desktop Alpha.

It launches the local Python Desktop Bridge and loads the static Desktop Lite UI.
The shell intentionally does **not** include the private quality engine, model router,
private evaluation data, or enterprise modules.

## Run

```bash
cd apps/desktop-electron
npm install
MEETING_AGENT_DESKTOP_WORKSPACE=../../demo_out/desktop_alpha_bundle npm start
```

Before running the shell, create a bundle:

```bash
PYTHONPATH=src python -m meeting_agent desktop-alpha-bundle --out-dir demo_out/desktop_alpha_bundle
```
