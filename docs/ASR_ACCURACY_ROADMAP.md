# ASR Accuracy Roadmap

## Goal

Pursue world-class transcription quality for AI Meeting Agent while keeping the Community Edition public-safe.

## Current Public Alpha position

The Public Alpha proves:

- real microphone capture
- audio diagnostics
- local ASR execution
- ASR to evidence-linked minutes
- private Quality Engine exclusion

It does not yet claim production-grade ASR accuracy.

## Accuracy strategy

World-class meeting transcription requires more than one ASR model.

Recommended pipeline:

1. Audio capture quality check
2. ASR model sweep
3. Japanese-aware normalization
4. CER-first evaluation for Japanese
5. Glossary and domain-term correction
6. Contextual correction
7. Evidence-linked minutes
8. Human review UI
9. Continuous benchmark tracking

## Model families to evaluate

Local/open models:

- faster-whisper small
- faster-whisper medium
- faster-whisper turbo
- faster-whisper large-v3
- Japanese fine-tuned Whisper / faster-whisper compatible models

Optional later:

- cloud ASR providers
- ensemble / voting
- speaker diarization
- word-level timestamp alignment

## Metrics

For Japanese, prioritize:

- CER
- normalized CER
- entity accuracy
- domain-term accuracy
- timestamp usability
- downstream minutes quality

WER can be misleading for Japanese because tokenization and whitespace are unstable.

## Quality tiers

### Public Alpha

- local ASR runs
- evidence-linked minutes generated
- quality limitations disclosed

### High-quality public-safe mode

- model sweep
- Japanese normalization
- glossary correction
- confidence reporting

### Private Quality Engine

- production Japanese correction
- private domain datasets
- advanced verifier / reranker
- entity-aware correction
- commercial-grade evaluation

## Non-goals for Community Edition

The Community Edition should not include:

- private evaluation datasets
- private Quality Engine code
- customer transcripts
- production private correction prompts

## Next implementation

Add an ASR Accuracy Lab script that runs multiple local ASR models against the same audio/reference pair and writes a public-safe metrics summary.
