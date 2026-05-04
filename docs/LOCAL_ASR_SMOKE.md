# Local ASR Smoke Workflow

v0.5 adds a lightweight ASR environment doctor. It checks optional dependencies without downloading models or starting heavy transcription.

## Check environment

```bash
meeting-agent asr-doctor --provider faster-whisper --out ./asr_doctor.json
```

## Install optional ASR support

```bash
pip install .[asr]
```

## Run local transcription

```bash
meeting-agent transcribe-audio ./audio.wav \
  --provider faster-whisper \
  --model-size small \
  --device cpu \
  --out ./meeting_from_audio.json
```

## Why this is separate from the public core

The public Community Edition should stay installable and testable without model downloads, GPU setup, or cloud API keys. Heavyweight ASR remains an optional provider path. Production-grade model routing, retry policy, and quality selection should live in the private commercial core.
