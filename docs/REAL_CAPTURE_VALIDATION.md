# Real Capture Validation Pack

This document describes the v1.4 private developer-preview workflow for validating real microphone capture without changing the publication hold policy.

## Status

- Publication gate remains on hold.
- Private Quality Engine is not included.
- Default workflow never opens the microphone.
- Live capture requires explicit consent flags and participant notification.

## Generate the validation pack

```bash
PYTHONPATH=src python -m meeting_agent capture-validation-pack \
  --out-dir capture_validation_pack \
  --duration-ms 3000
```

The pack includes:

- `README.md`
- `commands.md`
- `operator_checklist.md`
- `sidecar_template.txt`
- shell scripts for dry-run, live capture, post-capture minutes, and validation

## Validate after live capture

```bash
PYTHONPATH=src python -m meeting_agent capture-validation-run \
  --mic-dir mic_alpha_live \
  --minutes-dir mic_minutes_live \
  --out-json capture_validation_run.json \
  --out-md capture_validation_run.md
```

## Expected order

1. Run microphone dry-run.
2. Run live capture only after explicit consent.
3. Create or copy `audio.transcript.txt` if using sidecar ASR.
4. Run `microphone-to-minutes`.
5. Run `capture-validation-run`.
6. Review evidence-linked minutes before sharing.
