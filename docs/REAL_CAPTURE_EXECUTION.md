# Real Capture Execution

This private developer-preview workflow helps validate one short real microphone capture on the maintainer's Mac while keeping publication on hold.

## Generate the execution pack

```bash
PYTHONPATH=src python -m meeting_agent real-capture-execution-pack \
  --out-dir real_capture_execution_pack \
  --duration-ms 3000
```

The pack does **not** open the microphone. It writes scripts, commands, an operator checklist, and a sidecar template.

## Run live capture privately

Use the generated script or the command below after participants are notified:

```bash
PYTHONPATH=src python -m meeting_agent record-microphone-alpha \
  --out-dir mic_alpha_live \
  --duration-ms 3000 \
  --live \
  --confirm-live-recording \
  --notice-acknowledged \
  --participants-notified
```

## Generate post-capture minutes

```bash
PYTHONPATH=src python -m meeting_agent microphone-to-minutes \
  --mic-dir mic_alpha_live \
  --out-dir mic_minutes_live \
  --provider sidecar
```

## Run ASR to minutes

```bash
PYTHONPATH=src python -m meeting_agent asr-to-minutes \
  --audio-path mic_alpha_live/audio.wav \
  --provider sidecar \
  --sidecar mic_alpha_live/audio.transcript.txt \
  --reference mic_alpha_live/audio.transcript.txt \
  --out-dir asr_minutes_live
```

## Evaluate execution evidence

```bash
PYTHONPATH=src python -m meeting_agent real-capture-execution-gate \
  --mic-dir mic_alpha_live \
  --minutes-dir mic_minutes_live \
  --asr-minutes-dir asr_minutes_live \
  --out-json real_capture_execution_gate.json \
  --out-md real_capture_execution_gate.md
```

## Publication policy

This workflow is private. Keep `publication-gate` on hold until real capture, local ASR, launch assets, and maintainer approval all pass.
