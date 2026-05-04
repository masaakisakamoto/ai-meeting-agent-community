# Recording Safety Gate

The Community microphone alpha is private-development only. Live recording is never the default.

## Dry run

```bash
PYTHONPATH=src python -m meeting_agent recording-safety-gate --duration-ms 3000
PYTHONPATH=src python -m meeting_agent record-microphone-alpha --out-dir mic_alpha_out
```

## Blocked live request

```bash
PYTHONPATH=src python -m meeting_agent record-microphone-alpha --out-dir mic_alpha_out --live
```

This should produce a blocked report and must not open the microphone.

## Controlled live request

Only use this after participants are notified and the operator has acknowledged the recording notice.

```bash
PYTHONPATH=src python -m meeting_agent record-microphone-alpha \
  --out-dir mic_alpha_out \
  --duration-ms 3000 \
  --live \
  --confirm-live-recording \
  --notice-acknowledged \
  --participants-notified
```

The workflow writes local safety, notice, and audit artifacts.

## Bridge

```bash
curl -s -X POST http://127.0.0.1:8765/api/recording/safety-gate
```

The publication gate should remain on hold until public release criteria are explicitly met.
