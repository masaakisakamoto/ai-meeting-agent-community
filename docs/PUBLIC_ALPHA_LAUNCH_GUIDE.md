# Public Alpha Launch Guide

## Current decision

Public Alpha Candidate: GO  
Controlled technical review: GO  
Public release: HOLD

Do not make the repository public until the maintainer explicitly approves the unlock.

## Public positioning

AI Meeting Agent Community is a local-first Public Alpha Candidate for experimenting with:

- evidence-linked meeting minutes
- transcript ingestion
- action item extraction
- audio diagnostics
- controlled microphone alpha workflows
- local ASR validation with faster-whisper
- ASR to minutes workflows
- Desktop Alpha / local Bridge
- public/private core separation

This is not a production meeting recorder.

## What to say publicly

Safe public description:

> AI Meeting Agent Community is a local-first Public Alpha Candidate for evidence-linked meeting minutes, audio diagnostics, controlled microphone alpha workflows, and local ASR validation.

Safe short tagline:

> Local-first AI meeting minutes with evidence links, audio diagnostics, and local ASR workflows.

## What not to claim

Do not claim:

- production-ready meeting recording
- guaranteed ASR accuracy
- enterprise compliance
- signed native desktop installer
- system audio loopback support
- production-grade Japanese correction
- inclusion of the private Quality Engine

## Known limitations to mention

- Public Alpha Candidate only
- no signed native installer yet
- no system audio loopback capture yet
- ASR quality depends on local hardware, microphone, room noise, and model choice
- private Japanese Quality Engine is intentionally excluded
- enterprise SSO/RBAC/billing/compliance features are not included
- users must notify participants and obtain appropriate consent before recording

## Demo flow

Recommended demo sequence:

1. Show README status block.
2. Show Desktop Alpha / local Bridge UI.
3. Show evidence-linked ASR → Minutes HTML.
4. Show `publication-gate = hold`.
5. Show `docs/PRIVATE_CORE_BOUNDARIES.md`.
6. Explain that raw audio and generated evidence are not committed.
7. Explain known limitations clearly.

## Screenshot set

Minimum launch-quality screenshots:

1. Desktop Alpha UI / Bridge
2. ASR → Minutes HTML
3. Maintainer / evidence dashboard or release gate view

Do not include screenshots that expose raw meeting data, private transcripts, secrets, or private paths.

## Public announcement draft

Japanese:

> AI Meeting Agent Community の Public Alpha Candidate を準備しています。  
> ローカルファーストで、証跡つき議事録、音声診断、実マイクAlpha検証、faster-whisperによるローカルASR、Desktop Alpha / local Bridgeを試せるOSS候補です。  
> まだ本番用の会議録音ツールではありません。署名済みインストーラー、system audio loopback、本番品質の日本語補正エンジン、Enterprise機能は含めていません。  
> Community Editionとして公開できる範囲に限定し、Private Quality Engineは分離しています。

English:

> I’m preparing the Public Alpha Candidate for AI Meeting Agent Community.  
> It is a local-first experimental AI meeting assistant for evidence-linked minutes, audio diagnostics, controlled microphone alpha workflows, faster-whisper local ASR validation, and Desktop Alpha / local Bridge workflows.  
> It is not a production meeting recorder yet. It does not include a signed installer, system audio loopback, production Japanese Quality Engine, or enterprise compliance stack.  
> The Community Edition is intentionally open-core-ready while keeping the highest-value private quality components separate.

## Final unlock checklist

Before public unlock:

- [ ] README has been reviewed in GitHub UI.
- [ ] SECURITY.md has been reviewed.
- [ ] PRIVACY.md has been reviewed.
- [ ] THIRD_PARTY_NOTICES.md has been reviewed.
- [ ] LICENSE / NOTICE / TRADEMARK have been reviewed.
- [ ] main CI is green.
- [ ] public-alpha-candidate-v2.2 CI is green.
- [ ] `scripts/public_unlock_preflight.sh` passes.
- [ ] No raw audio/media files are tracked.
- [ ] No generated evidence directories are tracked.
- [ ] No private core code is tracked.
- [ ] Publication policy is intentionally updated by the maintainer.
- [ ] Repository visibility is intentionally changed by the maintainer.

## Rollback plan

If a problem is found after public unlock:

1. Make the repository private again if sensitive data is exposed.
2. Remove any exposed sensitive material.
3. Rotate any exposed credentials.
4. Re-run release-check, publication-gate, and CI.
5. Publish a correction if an announcement was already made.
6. Re-review private core boundaries.
