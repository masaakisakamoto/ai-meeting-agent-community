# v1.1 Private Alpha Candidate

This milestone keeps the repository private while preparing real microphone validation.

## What changed

- Developer environment doctor for Python/audio/ASR readiness.
- Private Alpha Gate that combines release readiness, publication hold, desktop packaging, microphone dry-run, and recording safety checks.
- Live capture plan generator that prints dry-run and live commands without opening the microphone.
- Desktop Bridge routes for environment, private-alpha gate, and capture-plan checks.
- UI buttons for Env Doctor, Private Alpha Gate, and Capture Plan.

## Policy

`publication-gate` must remain `hold` until the maintainer explicitly flips the publication policy.

Allowed:

- Local development
- Private repository
- Private portfolio review
- Controlled technical review
- Private alpha hardware validation

Blocked:

- Public GitHub repository
- SNS announcement
- Commercial landing page
- Public release blog

## Recommended local sequence

```bash
PYTHONPATH=src python3 -m meeting_agent dev-env-doctor --root . --out-json dev_environment.json --out-md dev_environment.md
PYTHONPATH=src python3 -m meeting_agent private-alpha-gate --root . --out-json private_alpha_gate.json --out-md private_alpha_gate.md
PYTHONPATH=src python3 -m meeting_agent live-capture-plan --out-json live_capture_plan.json --out-md live_capture_plan.md
```

Then create a Python 3.12 environment before live microphone capture.
