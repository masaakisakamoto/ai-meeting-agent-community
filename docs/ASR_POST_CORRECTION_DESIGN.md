# ASR Post-correction Design

## Goal

Improve Japanese ASR quality without including private Quality Engine code.

The Public Alpha path should support:

1. local ASR
2. public-safe glossary correction
3. before/after CER evaluation
4. evidence-linked minutes review
5. future human review UI

## Current design

This first implementation adds a wrapper-level post-correction hook.

It does not replace the core `asr-to-minutes` workflow yet.

The wrapper:

1. runs `meeting_agent asr-to-minutes`
2. reads `asr_validation/hypothesis.txt`
3. applies a public-safe glossary
4. compares normalized Japanese CER before and after correction
5. writes correction metrics under the selected output directory

## Why wrapper first

This keeps the change safe:

- no private Quality Engine code
- no private datasets
- no raw audio committed
- no changes to existing ASR-to-minutes behavior
- easy comparison before deeper CLI integration

## Next step

After enough samples:

- add an optional `--correction-glossary` argument to `asr-to-minutes`
- preserve corrected transcript artifacts
- optionally generate minutes from corrected transcript
- surface corrections in Desktop Alpha
- keep private production Japanese correction separate
