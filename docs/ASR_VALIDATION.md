# ASR Validation Workflow

This v1.4 private developer-preview workflow validates local ASR handoff after a capture without changing the publication hold policy.

## What it does

- Builds an ASR validation pack without opening the microphone.
- Validates sidecar transcription deterministically.
- Optionally checks faster-whisper readiness without downloading or running a model.
- Compares hypothesis text with a reference transcript using CER/WER.
- Keeps private-core code excluded and publication-gate on hold.

## Recommended commands

```bash
PYTHONPATH=src python -m meeting_agent asr-validation-pack \
  --out-dir asr_validation_pack

PYTHONPATH=src python -m meeting_agent asr-validation-run \
  --audio-path mic_alpha_live/audio.wav \
  --provider sidecar \
  --sidecar mic_alpha_live/audio.transcript.txt \
  --reference mic_alpha_live/audio.transcript.txt \
  --out-dir asr_validation_sidecar

PYTHONPATH=src python -m meeting_agent asr-validation-run \
  --audio-path mic_alpha_live/audio.wav \
  --provider faster-whisper \
  --out-dir asr_validation_faster_whisper \
  --dry-run
```

Use the faster-whisper live smoke only after optional ASR dependencies are installed in a Python 3.12 virtual environment.
