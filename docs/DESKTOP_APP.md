# Desktop App Strategy v0.3

v0.3 adds a verified **Desktop Lite** preview rather than a premature native app.
This is intentional: it creates a tangible product experience while keeping OS
microphone/system-audio permissions out of the public Community core.

## Current verified surface

```text
meeting-agent demo
  -> transcript/minutes/verification/quality outputs
  -> replay_events.json + replay_events.ndjson
  -> desktop_lite/index.html
  -> simulated_audio_manifest.json
```

The Desktop Lite UI is a static, dependency-free bundle. It can be opened in a
browser and later embedded in a Tauri or Electron WebView.

## Future native shell

```text
Tauri/Electron shell
  -> Desktop Lite web UI
  -> native audio commands
  -> audio provider interface
  -> local ASR provider or cloud Quality Engine
  -> transcript event stream
```

## Why real audio capture is still an extension point

Native audio capture differs by platform:

| Platform | Likely approach |
|---|---|
| macOS | CoreAudio, virtual devices such as BlackHole, permissions UX |
| Windows | WASAPI microphone and loopback capture |
| Linux | PipeWire / PulseAudio |

Shipping a fake "it records everything" implementation would be misleading. v0.3
therefore ships a deterministic simulated audio provider and a clean provider
interface. Production capture can be added without changing the transcript,
minutes, verifier, or UI layers.

## OSS/commercial boundary

Safe to keep public:

- Desktop Lite UI
- replay event schema
- audio provider interface
- simulated audio provider
- Tauri skeleton

Keep private/commercial:

- high-accuracy Japanese Quality Engine
- model router policies
- advanced realtime Verifier
- production diarization and speaker-name mapping
- private evaluation datasets
