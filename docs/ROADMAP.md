# Roadmap

## v0.1 Community foundation

- Transcript ingestion
- Evidence-linked minutes
- Basic verifier
- Markdown export
- Plugin registry
- CLI demo
- Unit tests

## v0.2 Desktop alpha

- Tauri/Electron shell
- Microphone capture
- System audio capture per OS
- Realtime transcript viewer
- Local Whisper integration
- Settings for BYOK / Ollama / LM Studio

## v0.3 Differentiation

- Japanese term dictionary
- Stronger action item extraction
- Evidence playback links
- Template gallery
- Obsidian / Notion / Google Docs export plugins

## v1.0 Hosted beta

- Cloud Quality Engine
- Team workspace
- Authentication
- Sharing and permissions
- Usage limits
- Billing

## v2 Enterprise

- SSO/SAML/OIDC
- RBAC
- Audit logs
- Data retention
- Private Cloud / on-prem
- Admin console
- SLA and support

## v0.6 completed: Packaged Desktop Alpha

- Desktop Alpha workspace generator
- Local Desktop Bridge server
- Bridge health / simulated recording / smoke APIs
- UI bridge panel
- Desktop Alpha smoke report
- Workspace launcher and manifest

## v0.5 completed: Local Audio Workflow Foundation

- Provider-neutral audio session workflow
- Simulated AudioChunk -> WAV persistence
- WAV inspection and replay provider
- Sidecar ASR provider for deterministic local demos
- Audio file -> transcript -> minutes CLI workflow
- Audio-linked evidence metadata via `audio_ref`

## v0.7 recommended: Real device UX and packaged app distribution

- Real microphone provider prototype
- OS-specific system audio strategy docs
- Desktop Lite bridge commands
- Tauri/Electron packaging path
- Local faster-whisper smoke workflow
- Audio quality diagnostics and preflight checks


## v0.8 completed: Real Microphone Alpha

- Safe-by-default microphone doctor and dry-run recording flow.
- Explicit live capture guard.
- Desktop Bridge microphone routes.
- Desktop UI microphone readiness controls.
- Publication gate remains on hold.

## v0.9 recommended: Live Microphone Validation on macOS

- Validate `sounddevice` on Python 3.12.
- Capture a real microphone WAV locally.
- Feed live capture into audio diagnostics.
- Connect UI to live capture start/stop with consent guardrails.


## v0.9 completed: Recording Safety Gate

- Live microphone capture is blocked unless explicit confirmation, recording notice acknowledgement, and participant notification are provided.
- Microphone alpha workflows write safety-gate, notice, and audit artifacts.
- Desktop Bridge exposes `/api/recording/safety-gate` and keeps publication-gate on hold.
