# ASR Post-correction Design

## Goal

Improve Japanese ASR review quality in the Community Edition without including private Quality Engine code, private datasets, production Japanese correction rules, or enterprise-only workflows.

The Public Alpha path supports:

1. local ASR or deterministic sidecar transcript input
2. public-safe glossary correction
3. before/after CER evaluation
4. optional minutes generation from the corrected transcript
5. corrected minutes review artifacts for human review
6. clear public/private boundary metadata

## Current integrated CLI status

ASR post-correction is integrated into the Community CLI through `meeting-agent asr-to-minutes`.

The correction path is optional and is enabled with `--correction-glossary`. Corrected minutes generation is enabled with `--generate-corrected-minutes`.

Example:

    PYTHONPATH=src python -m meeting_agent asr-to-minutes --audio-path mic_alpha_live/audio.wav --provider sidecar --sidecar mic_alpha_live/audio.transcript.txt --reference mic_alpha_live/audio.transcript.txt --correction-glossary configs/asr_correction_glossary_ja.example.json --generate-corrected-minutes --out-dir asr_minutes_corrected

When enabled, the workflow:

1. runs ASR validation through a Community-safe provider
2. reads the ASR hypothesis
3. applies a public-safe glossary
4. computes normalized Japanese CER before and after correction
5. preserves original and corrected transcript artifacts
6. optionally generates evidence-linked minutes from the corrected transcript
7. writes `private_core_included: false` in public-safe reports

The earlier `scripts/asr_post_correction_run.py` runner remains available as a maintainer utility, but the primary Public Alpha path is now the integrated CLI.

## Corrected minutes review

Maintainers can compare original and corrected ASR-to-minutes output directories with:

    PYTHONPATH=src python -m meeting_agent corrected-minutes-review --original-dir asr_minutes_original --corrected-dir asr_minutes_corrected --out-dir corrected_minutes_review

The review command writes:

- `review.md`
- `review.json`

These are local review artifacts. Do not commit generated review outputs, real meeting audio, real transcripts, screenshots, or private evidence bundles to the public repository.

## Public/private boundary

This design intentionally includes only:

- deterministic Community workflow code
- public-safe glossary examples
- local ASR/sidecar provider abstractions
- transparent before/after metrics
- evidence-linked minutes artifacts
- human review checklists

It intentionally excludes:

- private Quality Engine code
- private Japanese correction rules
- private evaluation datasets
- model-router scoring logic
- speaker-name mapping
- enterprise admin, billing, SSO, and hosted compliance controls

## Validation

The current regression coverage protects:

- `meeting-agent asr-to-minutes --correction-glossary --generate-corrected-minutes`
- actual glossary replacement on a public-safe sidecar fixture
- `applied_replacements_count > 0`
- CER after correction lower than before correction
- `private_core_included == false`
- `meeting-agent corrected-minutes-review` output generation

## Remaining work

The Community Edition still should not claim production-grade transcription or production-grade Japanese correction accuracy.

Future improvements can include:

- better public-safe example datasets
- clearer Desktop Alpha display of correction metadata
- additional local ASR model comparisons
- richer human review UI
- stronger public docs around limitations and reviewer expectations
