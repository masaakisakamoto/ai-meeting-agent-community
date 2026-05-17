# ASR to Minutes Workflow

`v1.4` adds a public-Community workflow that validates ASR output and immediately generates evidence-linked meeting minutes from the resulting transcript.

This workflow is designed for private developer preview. It does not include the private Quality Engine, model router, private evaluation data, speaker-name mapping, or enterprise modules.

## CLI

```bash
PYTHONPATH=src python -m meeting_agent asr-to-minutes \
  --audio-path mic_alpha_live/audio.wav \
  --provider sidecar \
  --sidecar mic_alpha_live/audio.transcript.txt \
  --reference mic_alpha_live/audio.transcript.txt \
  --out-dir asr_minutes_live
```

For local ASR smoke testing after optional dependencies are installed:

```bash
PYTHONPATH=src python -m meeting_agent asr-to-minutes \
  --audio-path mic_alpha_live/audio.wav \
  --provider faster-whisper \
  --model-size small \
  --device cpu \
  --out-dir asr_minutes_faster_whisper
```

## Generated artifacts

- `asr_validation/asr_validation_report.json`
- `asr_validation/transcript.asr.json`
- `meeting_from_asr.json`
- `minutes.json`
- `minutes.md`
- `minutes.html`
- `action_items.csv`
- `verification.json`
- `quality_gate.json`
- `replay_events.json`
- `desktop_lite/index.html`
- `asr_minutes_report.json`
- `asr_minutes_report.md`

## Bridge

```bash
curl -s -X POST http://127.0.0.1:8765/api/workflows/asr-to-minutes \
  -H "Content-Type: application/json" \
  -d '{"run_id":"ui_asr_minutes","provider":"sidecar"}'
```

## Public/private boundary

This workflow uses only Community-safe components:

- ASR provider abstraction
- Sidecar or optional faster-whisper provider
- Rule-based Community minutes generator
- Grounding verifier
- Quality gate
- HTML/CSV/Markdown exporters
- Desktop Lite UI bundle

It intentionally excludes:

- Private Quality Engine
- Advanced Japanese correction logic
- Model router scoring logic
- Private evaluation datasets
- Speaker-name mapping
- Enterprise admin, billing, SSO, and audit products

## Corrected minutes review CLI

After generating both original and corrected ASR minutes output directories, maintainers can create a side-by-side private review artifact:

```bash
meeting-agent corrected-minutes-review \
  --original-dir path/to/original_asr_minutes \
  --corrected-dir path/to/corrected_asr_minutes \
  --out-dir path/to/corrected_minutes_review \
  --title "Corrected ASR minutes review"
```

The command writes:

- `review.md`
- `review.json`

Use these outputs for private maintainer review of ASR correction quality, minutes deltas, and human review checklists. Do not publish real audio, transcripts, minutes, screenshots, or review artifacts unless they are explicitly sanitized.
