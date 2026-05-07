# AI Meeting Agent Community

**AI Meeting Agent Community** is a local-first, extensible prototype for building an AI meeting assistant: recording/transcript ingestion, evidence-linked meeting minutes, action item extraction, verification, plugin boundaries, and CLI workflows.

This repository is intentionally designed as an **open-core-ready Community Edition**:

- The community code is useful, hackable, and portfolio-friendly.
- The highest-value production quality engine can remain private and be attached through provider/plugin APIs.
- Optional ASR/LLM providers can be swapped without rewriting the product.

> Current implementation status: **v2.2 Public Alpha**.
>
> This Community Edition has validated the core local workflow: transcript ingestion, evidence-linked minutes, rule-based extraction, verification, exports, simulated audio, controlled real microphone alpha capture, local ASR smoke with faster-whisper, ASR → Minutes, Desktop Alpha Bridge, Evidence Export, Screenshot Readiness, and Public Alpha Candidate gates.
>
> This is **not production-ready**. It does not include a signed native installer, system audio loopback capture, production Japanese Quality Engine, enterprise admin/SSO/billing, or hosted compliance controls.
>
> Raw meeting audio should not be committed to this repository. Recording real meetings requires participant notice and appropriate consent.
>
> Public Alpha repository publication was intentionally unlocked by the maintainer. SNS announcements, commercial landing pages, and public release blogs remain blocked until separately approved.

---

## Features included in this source bundle


### v2.2 additions

- Evidence Export Pack for private README-ready evidence bundles without publishing.
- `evidence-export-pack`, `evidence-export-run`, and `evidence-export-gate` CLI workflows.
- Screenshot Automation Pack and Screenshot Readiness Gate for public-alpha screenshot planning.
- Desktop Bridge routes for `/api/evidence/export-*` and `/api/screenshots/*`.
- Desktop UI controls for Screenshot Pack/Gate and Evidence Export Pack/Run/Gate.
- Publication remains on hold; this version prepares launch evidence but does not publish.

### v2.1 additions

- Maintainer Review Pack for private release decision review without publishing.
- `maintainer-review-pack` CLI to generate maintainer decision matrix, evidence dashboard guide, public unlock risk review, and scripts.
- `maintainer-dashboard` / `maintainer-review-gate` CLI to build a private HTML/Markdown/JSON evidence dashboard.
- Desktop Bridge routes for `/api/maintainer/review-pack` and `/api/maintainer/dashboard`.
- Desktop UI controls for Maintainer Pack and Maintainer Dashboard.
- Publication remains on hold; this version is a private maintainer review workflow, not a public release.
### v2.0 additions

- Public Alpha Candidate Pack for private maintainer review without publishing.
- `public-alpha-candidate-pack` CLI to generate candidate README, final unlock checklist, release notes draft, rollback plan, security/privacy review, and scripts.
- `public-alpha-candidate-gate` CLI to evaluate final candidate readiness while publication remains on hold.
- Desktop Bridge routes for `/api/public-alpha/candidate-pack` and `/api/public-alpha/candidate-gate`.
- Desktop UI controls for Candidate Pack and Candidate Gate.
- Publication remains on hold; this is a private candidate workflow, not a public release.

### v1.9 additions

- Real Mac Evidence Collection Pack for collecting public-alpha evidence without opening the microphone during pack generation.
- `real-mac-evidence-pack` CLI to generate private evidence scripts, screenshot shotlist, sidecar template, and operator checklist.
- `real-mac-evidence-collect` CLI to collect live capture, ASR, launch asset, and screenshot evidence into one review directory.
- Desktop Bridge routes for `/api/evidence/real-mac-pack` and `/api/evidence/real-mac-collect`.
- Desktop UI controls for Evidence Pack and Collect Evidence.
- Public Alpha Readiness now tracks Real Mac evidence explicitly.

### v1.8 additions

- Launch Asset Pack generator for private Public Alpha draft materials without publishing.
- `launch-assets-pack` CLI to generate macOS quickstart, known limitations, screenshot guide, demo script, release draft, and launch checklist.
- `launch-polish-check` CLI to verify README expectations, generated launch assets, demo HTML, Desktop Alpha UI, and publication hold state.
- Desktop Bridge routes for `/api/launch/assets-pack` and `/api/launch/polish-check`.
- Desktop UI controls for Launch Assets and Launch Polish.
- Publication remains on hold; launch materials are private drafts only.

### v1.7 additions

- Local ASR smoke pack/run/gate for captured WAVs.
- Bridge/UI routes for local ASR smoke validation.
- Public Alpha Readiness now tracks local-ASR smoke evidence separately from deterministic sidecar checks.
- Publication remains on hold and private core is still excluded.

### v1.6 additions

- Real Microphone Validation Execution Pack for one short private Mac microphone validation run.
- `real-capture-execution-pack` CLI to generate scripts, checklist, sidecar template, and command plan without opening the microphone.
- `real-capture-execution-gate` CLI to evaluate live-capture evidence: safety gate, audit events, `audio.wav`, audio diagnostics, post-capture minutes, and ASR-to-minutes artifacts.
- Desktop Bridge routes for `/api/real-capture/execution-pack` and `/api/real-capture/execution-gate`.
- Desktop UI controls for Real Capture Pack and Real Capture Gate.
- Publication remains on hold; this version is still Private Developer Preview only.

### v1.5 additions

- Public Alpha Readiness gate for estimating announcement readiness while keeping publication blocked.
- `public-alpha-readiness` CLI to report blockers, estimates, and required milestones.
- `public-alpha-plan` CLI to generate the private version path toward public alpha.
- Desktop Bridge routes for `/api/public-alpha/readiness` and `/api/public-alpha/plan`.
- Desktop UI controls for Public Alpha Gate and Public Plan.
- Publication gate remains on hold; no public GitHub, SNS, landing page, or public blog announcement yet.

### v1.4 additions

- ASR to Minutes workflow for converting an ASR validation transcript into evidence-linked minutes.
- `asr-to-minutes` CLI with verification, quality gate, HTML/CSV/replay/UI outputs.
- Desktop Bridge route for `/api/workflows/asr-to-minutes`.
- Desktop UI control for ASR → Minutes.

### v1.3 additions

- ASR Validation Pack generator for sidecar and faster-whisper handoff checks without opening the microphone.
- `asr-validation-pack` CLI to generate README, commands, reference template, operator checklist, and scripts.
- `asr-validation-run` CLI to transcribe a known WAV, write `transcript.asr.json`, compare against reference text, and report CER/WER.
- Desktop Bridge routes for `/api/asr/validation-pack` and `/api/asr/validation-run`.
- Desktop UI controls for ASR Pack and Validate ASR.

### v1.2 additions

- Real Capture Validation Pack generator for private Mac microphone validation.
- `capture-validation-pack` CLI to generate README, commands, safety checklist, sidecar template, and scripts without opening the microphone.
- `capture-validation-run` CLI to validate live-capture artifacts, safety gate, audit log, audio quality, and post-capture minutes.
- Desktop Bridge routes for `/api/capture/validation-pack` and `/api/capture/validation-run`.
- Desktop UI controls for Validation Pack and Validate Capture.
- Publication gate remains on hold; no public OSS release or announcement yet.

### v1.1 additions

- Post-capture gate for microphone alpha artifacts.
- `microphone-to-minutes` CLI workflow for existing WAV files.
- Audio diagnostics, level meter, sidecar/local-ASR transcription, evidence-linked minutes, HTML, CSV, replay events, and Desktop Lite bundle from a captured microphone WAV.
- Desktop Bridge routes for `/api/post-capture/gate` and `/api/workflows/microphone-to-minutes`.
- UI controls for Post Capture Gate and Mic → Minutes.
- Publication gate remains on hold; no public OSS release or announcement yet.

### v1.0 additions

- Private Alpha Gate for controlled local validation while publication remains blocked.
- Developer Environment Doctor for Python/runtime/audio/ASR readiness.
- Live Capture Plan generator that does not open the microphone.
- Desktop Bridge routes for environment, private-alpha gate, and capture plan.
- Python 3.12 macOS setup script for optional audio dependencies.

### v0.9 additions

- Recording safety gate for any live microphone request.
- Explicit confirmation, recording notice acknowledgement, and participant-notification checks before opening a real microphone.
- Local audit trail and recording notice artifacts for microphone alpha workflows.
- Desktop Bridge route for `/api/recording/safety-gate`.
- Publication gate remains on hold until the maintainer explicitly flips the policy.

### v0.8 additions

- Real Microphone Alpha module with safe-by-default dry-run behavior
- Microphone doctor / preflight reports for optional audio dependencies
- `record-microphone-alpha` CLI command with explicit `--live` guard for real capture
- Desktop Bridge microphone doctor and microphone alpha dry-run routes
- Desktop UI controls for Mic Doctor and Mic Alpha Dry Run
- Python 3.12-oriented microphone setup guide
- Publication gate remains on hold until public announcement criteria are met

### v0.7 additions

- Desktop Alpha workspace generator with local manifest
- Local Desktop Bridge server on `127.0.0.1`
- UI bridge actions for health, simulated recording, and smoke workflow
- Deterministic Desktop Alpha smoke report
- Workspace launcher script and Desktop Alpha README generation
- Public/private boundary metadata in the desktop manifest

### v0.5 additions

- Optional real microphone capture provider through `sounddevice`
- Capture readiness / preflight checks before recording
- Deterministic WAV audio quality diagnostics
- Local ASR environment doctor for `faster-whisper`
- Audio device listing CLI
- Short microphone recording CLI with WAV + manifest + quality report
- Native capture strategy, audio quality, and local ASR smoke documentation

### v0.4 additions

- Provider-neutral audio session workflow
- Simulated AudioChunk capture persisted as WAV
- WAV inspection utility
- WAV file replay provider
- Sidecar transcript ASR provider for deterministic local audio demos
- Audio file → transcript → evidence-linked minutes workflow
- Audio-linked transcript segments with `audio_ref` evidence metadata

### v0.3 additions

- Dependency-free Desktop Lite UI bundle
- Simulated realtime transcript playback
- Replay event JSON / NDJSON generation
- Audio capture provider interface
- CI-safe simulated audio capture provider
- Tauri desktop app skeleton for future native shell
- UI export workflow from the CLI

### v0.2 additions

- Glossary-based Japanese term canonicalization
- Evidence-linked HTML report export
- Action item CSV export
- Local SQLite meeting store
- Deterministic minutes quality gate
- Recording/transcription consent notice helper
- Plugin manifest validation
- Lightweight SBOM generation
- OSS release readiness gate

### Working core

- Plain-text and JSON transcript ingestion
- Timestamped segment model
- Evidence-linked decisions, action items, open questions, and risks
- Japanese-oriented rule-based extraction baseline
- Verification report for missing evidence and weak grounding
- Markdown and JSON export
- Basic PII redaction
- CER/WER evaluation utilities
- Plugin registry and provider interfaces
- CLI commands
- Unit tests

### Extension-ready architecture

- ASR provider interface
- LLM provider interface
- Minutes generator interface
- Verifier boundary
- Exporter plugin pattern
- Optional `faster-whisper` provider stub
- Optional OpenAI-compatible provider stub
- Optional FastAPI app factory
- Open-core private module boundaries documented

---

## Quick start

```bash
cd ai-meeting-agent-community
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e .

meeting-agent demo --out-dir ./demo_out
```

Or without installing:

```bash
PYTHONPATH=src python3 -m meeting_agent demo --out-dir ./demo_out
```

You should get:

```text
demo_out/meeting.json
demo_out/minutes.json
demo_out/minutes.md
demo_out/verification.json
demo_out/desktop_lite/index.html
demo_out/replay_events.json
demo_out/simulated_audio_manifest.json
demo_out/audio.wav
demo_out/audio_session.json
demo_out/audio_info.json
demo_out/audio_quality.json
demo_out/capture_readiness.json
demo_out/asr_doctor.json
demo_out/audio_devices.json
demo_out/meeting_from_audio.json
demo_out/audio_workflow/minutes.md
demo_out/desktop_alpha_bundle/desktop_lite/index.html
demo_out/desktop_alpha_bundle/desktop_alpha_manifest.json
demo_out/desktop_alpha_report.json
```

---

## CLI examples

### Ingest a transcript

```bash
meeting-agent ingest examples/sample_meeting_ja.txt \
  --meeting-id mtg_demo_ja \
  --title "AI Meeting Agent MVP" \
  --out ./meeting.json
```

### Generate evidence-linked minutes

```bash
meeting-agent minutes ./meeting.json \
  --out-json ./minutes.json \
  --out-md ./minutes.md
```


### Apply glossary corrections

```bash
meeting-agent apply-glossary ./meeting.json examples/glossary_ja.json \
  --out ./meeting.corrected.json \
  --report ./glossary_report.json
```

### Export HTML and action CSV

```bash
meeting-agent export-html ./meeting.json ./minutes.json --out ./minutes.html
meeting-agent export-actions-csv ./meeting.json ./minutes.json --out ./action_items.csv
```

### Run quality gate and OSS release readiness

```bash
meeting-agent quality-gate ./meeting.json ./minutes.json ./verification.json --out ./quality_gate.json
meeting-agent release-check --root . --run-tests --out-json ./release_check.json --out-md ./release_check.md
```

### Generate consent notice and lightweight SBOM

```bash
meeting-agent consent-notice --out ./recording_notice.md
meeting-agent sbom --root . --out ./sbom.json
```

### Build Desktop Lite UI bundle

```bash
meeting-agent ui-bundle ./meeting.json   --minutes-json ./minutes.json   --out-dir ./desktop_lite
```

Open `desktop_lite/index.html` in a browser to run the simulated realtime transcript UI.

### Build, smoke-test, package-check, and serve Desktop Alpha

```bash
meeting-agent desktop-alpha-bundle \
  --out-dir ./desktop_alpha_out

meeting-agent desktop-smoke \
  --workspace ./desktop_alpha_out \
  --out-json ./desktop_alpha_out/desktop_alpha_smoke.json \
  --out-md ./desktop_alpha_out/desktop_alpha_smoke.md

meeting-agent desktop-package-check \
  --root . \
  --out-json ./desktop_package_check.json \
  --out-md ./desktop_package_check.md

meeting-agent desktop-serve \
  --workspace ./desktop_alpha_out \
  --ui-dir ./desktop_alpha_out/desktop_lite \
  --open-browser
```

`desktop-serve` binds to `127.0.0.1` and exposes local Community APIs for bridge health,
simulated recording, and deterministic smoke workflows. It intentionally excludes private
quality-engine internals.

### Generate deterministic transcript replay events

```bash
meeting-agent replay-transcript ./meeting.json --out ./replay_events.json --format json
meeting-agent replay-transcript ./meeting.json --out ./replay_events.ndjson --format ndjson
```

### Simulate audio capture without accessing a microphone

```bash
meeting-agent simulate-audio --out ./simulated_audio_manifest.json --total-ms 3000 --chunk-ms 250
```

### Persist simulated audio as WAV

```bash
meeting-agent record-simulated --out-dir ./audio_demo --total-ms 3000 --chunk-ms 250
meeting-agent inspect-audio ./audio_demo/audio.wav --out ./audio_demo/audio_info.json
meeting-agent audio-quality ./audio_demo/audio.wav --out ./audio_demo/audio_quality.json
```

### Check capture readiness and audio devices

```bash
meeting-agent list-audio-devices --provider simulated
meeting-agent capture-readiness --provider simulated --out ./capture_readiness.json
```

For real microphone smoke tests, install optional audio support first:

```bash
pip install .[audio]
meeting-agent list-audio-devices --provider microphone
meeting-agent capture-readiness --provider microphone --require-real-device
meeting-agent record-microphone --out-dir ./mic_demo --duration-ms 3000
```

### Check local ASR environment

```bash
meeting-agent asr-doctor --provider faster-whisper --out ./asr_doctor.json
```

### Audio file → transcript → minutes workflow

For deterministic OSS demos, place a sidecar transcript beside the WAV file, for example
`audio.transcript.txt` or `audio.transcript.json`, then run:

```bash
meeting-agent transcribe-audio ./audio_demo/audio.wav \
  --provider sidecar \
  --sidecar examples/sample_meeting_ja.txt \
  --meeting-id mtg_audio_demo \
  --title "Audio Workflow Demo" \
  --out ./audio_demo/meeting_from_audio.json

meeting-agent audio-to-minutes ./audio_demo/audio.wav \
  --provider sidecar \
  --sidecar examples/sample_meeting_ja.txt \
  --out-dir ./audio_minutes
```

Use `--provider faster-whisper` after installing `pip install .[asr]` to connect a real local ASR model.

### Verify grounding

```bash
meeting-agent verify ./meeting.json ./minutes.json \
  --out ./verification.json
```

### Redact PII from a transcript JSON

```bash
meeting-agent redact ./meeting.json --out ./meeting.redacted.json
```

### Evaluate ASR output

```bash
meeting-agent eval-text --reference ./ref.txt --hypothesis ./hyp.txt
```

### Check OSS release readiness

```bash
meeting-agent readiness --root . \
  --out-json release_readiness.json \
  --out-md release_readiness.md
```

Use this before publishing. It checks required public files, package metadata, compileability, examples, public/private boundaries, and obvious secret leakage.

---

## Example input format

```text
[00:00:01] 佐藤: 今日の議題はAI会議エージェントのMVPです。
[00:00:25] 佐藤: v0.1はローカル録音、文字起こし、Markdown出力で進めることで決定します。
[00:00:45] 田中: 鈴木さん、来週中にTauriの音声取得を調査お願いします。
```

Supported formats:

- `[HH:MM:SS] Speaker: text`
- `[MM:SS] Speaker: text`
- `Speaker: text`
- Raw paragraphs
- JSON transcript produced by this project

---

## Open-core strategy

Recommended public/private split:

### Public Community Edition

- Desktop/web shell
- Transcript viewer
- Local storage
- Basic local ASR adapters
- Basic minutes generator
- Markdown export
- Plugin SDK
- Public benchmark runner

### Private Quality Engine

- High-accuracy Japanese meeting generator
- Model router
- Verifier pipeline
- Japanese term correction
- Speaker-name mapping
- Private evaluation dataset
- Enterprise security/admin/billing
- Advanced integrations

See [`docs/OPEN_CORE_STRATEGY.md`](docs/OPEN_CORE_STRATEGY.md).

---

## Repository layout

```text
src/meeting_agent/
  core/             # schemas, transcript parsing, plugin registry
  intelligence/     # minutes generation, verification
  exporters/        # markdown/json/html/csv exporters
  providers/        # ASR, LLM, and audio provider interfaces/adapters
  streaming/        # replay events and realtime transcript primitives
  ui/               # Desktop Lite static UI assets
  desktop/          # local Desktop Alpha bridge and workspace helpers
  security/         # redaction helpers
  evals/            # WER/CER and quality metrics
  streaming/        # realtime buffer primitives
  api/              # optional FastAPI app factory
  plugins/          # plugin examples
examples/           # Japanese sample meeting
configs/            # default templates
scripts/            # helper scripts
tests/              # unit tests
```

---

## Design principles

1. **Evidence first**: Every important generated item should point back to transcript segments.
2. **Provider-agnostic**: ASR/LLM models are replaceable.
3. **Local-first**: Community version should run without server cost.
4. **Open shell, protected core**: OSS interface and basic functionality, private quality engine for commercial moat.
5. **Evaluation-driven**: Quality should be measured, not guessed.

---

## Public OSS release timing

Do not publish merely because the code runs. Publish when the project is safe, useful, and strategically positioned.

Recommended minimum gates:

- `python -m compileall -q src tests` passes.
- `python -m unittest discover -s tests -v` passes.
- `meeting-agent demo --out-dir ./demo_out` works on a clean environment.
- `meeting-agent readiness --root .` returns `pass`.
- No private prompts, private evaluation data, credentials, real meeting transcripts, or commercial-only internals are included.

See [`docs/OSS_RELEASE_CHECKLIST.md`](docs/OSS_RELEASE_CHECKLIST.md) and [`docs/PUBLIC_RELEASE_GATE.md`](docs/PUBLIC_RELEASE_GATE.md).

## License

Apache-2.0 for this Community prototype. See [`LICENSE`](LICENSE).

This is not legal advice. For commercial usage, review all third-party dependencies and model/API terms.


## Launch asset preview

Publication is intentionally on hold. To prepare launch materials privately:

```bash
PYTHONPATH=src python3 -m meeting_agent launch-assets-pack --out-dir launch_assets
PYTHONPATH=src python3 -m meeting_agent launch-readiness-gate --root . --launch-assets-dir launch_assets
```

Do not create a public GitHub repository, SNS announcement, commercial landing page, or public release blog until `publication-gate` is explicitly changed by the maintainer and all real microphone / local ASR gates pass.


## v2.1 Private Developer Preview

Adds Public Alpha Candidate Pack and Candidate Gate for private pre-launch review. Publication remains on hold until maintainer approval, real Mac evidence, local ASR smoke, screenshots, and final README review are complete.
