# Local Audio Workflow

The Community repository intentionally keeps real OS audio capture optional, but
v0.5 defines the stable path every capture provider must follow.

## Pipeline

```text
AudioCaptureProvider.capture(config, session_id)
  -> Iterable[AudioChunk]
  -> write_wav_from_chunks(...)
  -> audio.wav + audio_session.json
  -> ASRProvider.transcribe_file(...)
  -> Transcript with per-segment audio_ref
  -> evidence-linked minutes
```

## Commands

```bash
meeting-agent record-simulated --out-dir ./audio_demo --total-ms 3000 --chunk-ms 250
meeting-agent inspect-audio ./audio_demo/audio.wav --out ./audio_demo/audio_info.json
```

For deterministic demos, bind a WAV to a sidecar transcript:

```bash
meeting-agent transcribe-audio ./audio_demo/audio.wav \
  --provider sidecar \
  --sidecar examples/sample_meeting_ja.txt \
  --meeting-id mtg_audio_demo \
  --title "Audio Workflow Demo" \
  --out ./audio_demo/meeting_from_audio.json
```

Generate minutes directly from audio:

```bash
meeting-agent audio-to-minutes ./audio_demo/audio.wav \
  --provider sidecar \
  --sidecar examples/sample_meeting_ja.txt \
  --out-dir ./audio_minutes
```

## Provider strategy

Public OSS providers:

- simulated audio provider
- WAV file replay provider
- sidecar transcript provider
- optional faster-whisper adapter

Private/commercial providers can be added behind the same interfaces:

- model-router ASR
- diarization-aware ASR
- Japanese terminology correction
- speaker-name mapping
- high-assurance verifier

## Why sidecar ASR exists

`SidecarTranscriptProvider` is not a speech recognition model. It is a deterministic
workflow tool that lets the repository test and demo audio-linked transcripts
without requiring GPU, microphone permissions, or cloud APIs.

This keeps the public project easy to run while preserving a clean seam for real
local ASR or the private Quality Engine.
