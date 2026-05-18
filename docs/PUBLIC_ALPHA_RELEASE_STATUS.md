# Public Alpha Release Status

## Current decision

Public Alpha repository publication: GO  
Controlled technical review: GO  
Production release: NO

The maintainer intentionally unlocked Public Alpha repository publication.

This project is still a Public Alpha, not a production-ready meeting recorder.

## What is validated

- Clean source candidate
- main branch CI
- release-check
- unit tests
- issue templates
- required public documents
- no tracked raw audio/media
- no tracked generated evidence directories
- no tracked pycache or macOS metadata
- no tracked personal absolute paths
- private core excluded

## Still not included

- signed native installer
- system audio loopback capture
- production Japanese Quality Engine
- enterprise SSO/RBAC/billing/compliance stack
- guaranteed ASR accuracy across environments

## Still blocked

The following remain blocked until separately approved:

- SNS announcement
- commercial landing page
- public release blog

## Public Alpha safety rules

Do not commit:

- raw audio
- private transcripts
- generated evidence directories
- credentials
- private Quality Engine code
- private evaluation datasets

Do not record meetings without participant notice and appropriate consent.

## ASR correction and review status

Recent Public Alpha validation includes a Community-safe ASR correction and review path:

- `meeting-agent asr-to-minutes --correction-glossary --generate-corrected-minutes`
- `meeting-agent corrected-minutes-review`
- public-safe positive regression coverage for actual glossary replacement
- before/after CER metrics
- corrected transcript artifacts
- corrected minutes review artifacts
- `private_core_included: false` checks

This improves maintainer reviewability of ASR output. It does not mean production-grade Japanese transcription or production-grade correction accuracy.
