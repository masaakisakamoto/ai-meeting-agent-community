# Tauri Desktop App Skeleton

This is an intentionally minimal scaffold for the future native desktop app.
The verified v0.6 implementation ships a dependency-free Desktop Lite UI and a
local Python Desktop Bridge that can be embedded or launched from a desktop shell.

## Target architecture

```text
Tauri shell
  -> WebView UI from Desktop Lite
  -> local Python Desktop Bridge on 127.0.0.1
  -> optional native audio capture commands
  -> transcript replay or streaming ASR events
  -> evidence-linked minutes export
```

## Verified alpha runtime

```bash
PYTHONPATH=src python -m meeting_agent desktop-alpha --workspace ./desktop_alpha_out
PYTHONPATH=src python -m meeting_agent desktop-serve --workspace ./desktop_alpha_out --open-browser
```

## Why native capture remains optional

Real microphone and system-audio capture differ by OS:

- macOS: CoreAudio / virtual devices such as BlackHole
- Windows: WASAPI loopback
- Linux: PipeWire / PulseAudio

The Community repository keeps those providers optional so OSS users can run the
repo without granting device permissions. Production-grade capture can be added
through the audio provider interface under `src/meeting_agent/providers/audio`.
