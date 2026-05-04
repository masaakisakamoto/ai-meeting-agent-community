# Architecture

## Product shape

```text
Community Shell
  ├─ Desktop/Web UI
  ├─ Recorder
  ├─ Transcript Viewer
  ├─ Local ASR adapters
  ├─ Basic Minutes Generator
  ├─ Markdown/Local Export
  └─ Plugin SDK
        ↓ provider interfaces
Private Quality Engine
  ├─ Model Router
  ├─ Japanese Term Correction
  ├─ Evidence-linked Generator
  ├─ Verifier Pipeline
  ├─ Speaker Name Mapping
  ├─ Private Evaluation Datasets
  └─ Enterprise Security / Billing / Admin
```

## Core interfaces

- `ASRProvider`: file and stream transcription
- `LLMProvider`: model generation
- `MinutesGenerator`: transcript to structured minutes
- `MinutesVerifier`: grounding check
- `IntegrationAdapter`: publish minutes / create tasks
- `Exporter`: Markdown, Obsidian, Google Docs, Notion, etc.

## Why this architecture

- Fast v0.1 release using rule-based local logic
- Easy replacement with commercial/private quality modules
- OSS plugin ecosystem without exposing the moat
- Evidence and verification are first-class from day one

## Data flow

```text
Transcript input / ASR
  → TranscriptSegment[]
  → RuleBasedMinutesGenerator or QualityEngineGenerator
  → MinutesDraft with evidence IDs
  → MinutesVerifier
  → Markdown/JSON/Integrations
```
