# Native Capture Strategy

This document defines how Community Edition approaches audio capture without compromising OSS safety or future commercial extensibility.

## Principles

1. **Provider-neutral core.** The core pipeline accepts `AudioChunk` objects and does not depend on one OS or audio library.
2. **No surprise microphone access.** Readiness checks and device listing do not start recording.
3. **Optional native dependencies.** Real microphone capture is behind `pip install .[audio]`.
4. **System audio is a separate provider family.** PC/internal meeting audio differs by OS and should not be mixed into the microphone provider.
5. **Commercial quality remains private.** Capture plumbing can be public; production model routing and high-quality meeting intelligence can remain closed.

## Provider roadmap

| Provider | Status | Notes |
|---|---|---|
| `simulated-audio` | Implemented | CI-safe, deterministic demo audio. |
| `wav-file` | Implemented | Replays existing WAV files as chunks. |
| `sounddevice-microphone` | Implemented as optional | Short microphone recording through `sounddevice`. |
| macOS system audio | Planned | CoreAudio + user-selected virtual device such as BlackHole/Loopback. |
| Windows system audio | Planned | WASAPI loopback. |
| Linux system audio | Planned | PipeWire/PulseAudio monitor source. |
| Browser capture | Planned | Web Audio API bridge. |
| Meeting bot capture | Planned | Zoom/Meet/Teams bot provider. |

## Recommended rollout

1. Keep simulated audio as default for demos and CI.
2. Add microphone recording for local smoke tests.
3. Add audio quality diagnostics to every captured WAV.
4. Add local ASR smoke workflow.
5. Add OS-specific system-audio providers only after the Desktop App shell is ready.
