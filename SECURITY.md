# Security policy

AI Meeting Agent Community is a Public Alpha Candidate, not a production-ready meeting recorder.

Do not process sensitive production meeting data without reviewing storage, access control, deletion, sharing, and retention behavior.

## Reporting security issues

If this repository is public, do not disclose sensitive vulnerability details in a public issue before triage.

Preferred reporting paths:

- Use GitHub Security Advisories if enabled.
- Otherwise, contact the maintainer privately.
- If a public issue is necessary, describe the affected area at a high level and avoid secrets, raw meeting audio, personal data, or exploit details.

## Data handling

- Do not commit raw microphone recordings or meeting audio.
- Do not commit private transcripts, customer data, API keys, or credentials.
- Do not commit generated evidence directories such as `mic_alpha_live/`, `real_mac_evidence/`, `evidence_export/`, or `screenshots/`.
- Treat transcripts, summaries, and action items as potentially sensitive.

## Recommended production controls

Before production or commercial use, add and verify:

- encryption for audio, transcript, and notes storage
- authentication and RBAC
- retention and deletion controls
- consent logging
- audit logging
- PII detection and redaction
- hosted API rate limits and abuse controls
- secure secret management
- dependency and license scanning
- incident response and rollback process

## Current alpha guardrails

- Publication is blocked by `configs/publication_policy.json` until maintainer approval.
- The private Quality Engine is intentionally excluded from the Community repository.
- Recording workflows require explicit confirmation and participant-notification acknowledgement.
