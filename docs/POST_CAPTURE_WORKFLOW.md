# Post-Capture Microphone Minutes Workflow

This private developer-preview workflow turns a validated microphone WAV artifact into evidence-linked minutes without including the private Quality Engine.

## Purpose

After a controlled microphone alpha capture produces `audio.wav`, the Community workflow can:

1. inspect WAV metadata,
2. run audio quality diagnostics,
3. generate level-meter frames,
4. transcribe via deterministic sidecar or optional local ASR,
5. generate evidence-linked minutes,
6. verify grounding,
7. export Markdown, HTML, CSV, replay events, and a Desktop Lite review bundle.

## Safety boundary

This workflow **does not open the microphone**. It only processes an existing audio file. Real capture must still pass the recording safety gate.

## Deterministic sidecar workflow

```bash
PYTHONPATH=src python -m meeting_agent post-capture-gate \
  --mic-dir mic_alpha_out \
  --provider sidecar \
  --out-json post_capture_gate.json \
  --out-md post_capture_gate.md

PYTHONPATH=src python -m meeting_agent microphone-to-minutes \
  --mic-dir mic_alpha_out \
  --provider sidecar \
  --out-dir mic_minutes_out
```

If `audio.transcript.txt` is missing, the workflow creates a deterministic developer-preview sidecar so UI, export, and verification paths remain testable.

## Optional local ASR workflow

```bash
PYTHONPATH=src python -m meeting_agent asr-doctor --provider faster-whisper
PYTHONPATH=src python -m meeting_agent microphone-to-minutes \
  --mic-dir mic_alpha_out \
  --provider faster-whisper \
  --out-dir mic_minutes_out
```

## Public/private boundary

Included:

- audio quality diagnostics,
- level meter frames,
- ASR provider interface,
- sidecar smoke workflow,
- evidence-linked Community minutes,
- grounding verifier,
- Desktop Lite review bundle.

Excluded:

- Private Quality Engine,
- advanced Japanese correction,
- model router decision logic,
- private evaluation datasets,
- enterprise admin/billing/SSO.
