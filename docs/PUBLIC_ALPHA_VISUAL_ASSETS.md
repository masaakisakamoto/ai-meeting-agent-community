# Public Alpha Visual Assets Plan

This document defines safe visual assets for the Public Alpha repository.

## Goal

Improve the GitHub README experience without exposing:

- raw meeting audio
- private transcripts
- generated evidence directories
- credentials
- private Quality Engine code
- private evaluation datasets
- personal absolute paths

## Safe public asset directory

Use:

```text
docs/assets/public-preview/
```

Do not use:

```text
screenshots/
real_mac_evidence/
evidence_export/
maintainer_dashboard/
public_alpha_candidate/
mic_alpha_live/
asr_minutes_faster_whisper/
```

Those names are reserved for generated/private evidence workflows and may be blocked by CI.

## Recommended README visuals

Minimum recommended set:

1. Desktop Alpha / local Bridge overview
2. Evidence-linked minutes HTML preview
3. Public Alpha safety / release-check view

Optional later:

4. ASR workflow diagram
5. Public/private core boundary diagram
6. Local-first architecture diagram

## Sanitization checklist

Before committing any image:

- [ ] No raw meeting content
- [ ] No private transcripts
- [ ] No personal names unless demo/fake
- [ ] No local absolute paths
- [ ] No tokens, keys, or credentials
- [ ] No private repository-only URLs
- [ ] No private Quality Engine details
- [ ] No generated real evidence from private sessions

## Recommended filenames

Use descriptive public-safe names:

```text
docs/assets/public-preview/desktop-alpha-bridge.png
docs/assets/public-preview/evidence-linked-minutes.png
docs/assets/public-preview/release-safety-checks.png
```

## README placement

Add visuals after the Try it in 5 minutes section and before the feature history.

Suggested section title:

```markdown
## Public Alpha preview
```

## Current decision

Visual assets are planned, but not required for the current Public Alpha prerelease.

SNS announcement remains on hold until the README visual assets are reviewed.
