# Public Alpha Go / No-Go Review

## Current decision

Status: Public Alpha Candidate  
Public release: HOLD  
Decision: Do not unlock publication until maintainer explicitly approves.

## Candidate evidence

- Release check: pass
- Publication gate: hold
- Real Mac microphone capture evidence: pass
- Audio quality diagnostics: pass
- faster-whisper local ASR smoke: pass
- ASR to evidence-linked minutes: pass
- Real Mac evidence collection: pass
- Evidence export: pass
- Screenshot readiness: pass
- Private core excluded: pass

## Remaining unlock gate

Publication remains blocked by `configs/publication_policy.json`.

Before public release, maintainer must explicitly approve:

- README and launch copy
- Known limitations
- Security and privacy posture
- Private core boundary
- No raw audio committed
- No secrets committed
- No generated evidence directories committed
- No accidental private modules
- Rollback plan

## Recommended decision

Controlled technical review: GO  
Private portfolio review: GO  
Public Alpha Candidate: GO  
Public announcement: HOLD until maintainer approval
