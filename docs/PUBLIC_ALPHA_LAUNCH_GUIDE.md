# Public Alpha Launch Guide

## Current decision

Public Alpha repository publication: GO  
Controlled technical review: GO  
Production release: NO

This project is now prepared for Public Alpha repository publication, but it is not production-ready.

## Public positioning

AI Meeting Agent Community is a local-first Public Alpha for experimenting with:

- evidence-linked meeting minutes
- transcript ingestion
- action item extraction
- audio diagnostics
- controlled microphone alpha workflows
- local ASR validation with faster-whisper
- ASR to minutes workflows
- Desktop Alpha / local Bridge
- public/private core separation

## What to say publicly

Safe public description:

> AI Meeting Agent Community is a local-first Public Alpha for evidence-linked meeting minutes, audio diagnostics, controlled microphone alpha workflows, and local ASR validation.

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

- Public Alpha only
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
4. Show `docs/PRIVATE_CORE_BOUNDARIES.md`.
5. Explain that raw audio and generated evidence are not committed.
6. Explain known limitations clearly.

## Rollback plan

If a problem is found after public unlock:

1. Make the repository private again if sensitive data is exposed.
2. Remove any exposed sensitive material.
3. Rotate any exposed credentials.
4. Re-run release-check and CI.
5. Publish a correction if an announcement was already made.
6. Re-review private core boundaries.
