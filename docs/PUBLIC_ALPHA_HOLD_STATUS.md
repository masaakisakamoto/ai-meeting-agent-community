# Public Alpha HOLD Status

## Current decision

Public Alpha Candidate: GO  
Controlled technical review: GO  
Public release: HOLD

The repository must remain private until the maintainer intentionally unlocks publication.

## What is already validated

- Clean source candidate
- main branch CI
- public-alpha-candidate-v2.2 branch CI
- release-check
- publication-gate
- unit tests
- issue templates
- required public documents
- no tracked raw audio/media
- no tracked generated evidence directories
- no tracked pycache or macOS metadata
- no tracked personal absolute paths
- private core excluded

## Still blocked

The following remain intentionally blocked until explicit maintainer approval:

- public GitHub repository
- SNS announcement
- commercial landing page
- public release blog

## Unlock rule

Do not unlock publication by accident.

Unlock requires all of the following:

1. Maintainer explicitly approves public release.
2. `configs/publication_policy.json` is intentionally updated.
3. Repository visibility is intentionally changed from private to public.
4. README, SECURITY, PRIVACY, THIRD_PARTY_NOTICES, and LICENSE are reviewed.
5. CI is green after the final change.
6. No raw audio, private transcript, generated evidence, or private core code is committed.

## Current recommendation

Keep HOLD.
