# Public Alpha Candidate Workflow

v2.2 includes a private Public Alpha Candidate workflow. It is designed to answer one question:

> Are we ready to unlock publication, or should the repository remain private?

The workflow intentionally does **not** publish anything. It keeps `publication-gate` on hold until the maintainer explicitly changes the publication policy.

## Commands

```bash
PYTHONPATH=src python -m meeting_agent public-alpha-candidate-pack --out-dir public_alpha_candidate
PYTHONPATH=src python -m meeting_agent public-alpha-candidate-gate --root . --candidate-dir public_alpha_candidate
```

## Candidate criteria

- Release hygiene passes.
- Publication policy remains intentional.
- Real Mac evidence is collected.
- Local ASR smoke is collected.
- Launch assets and screenshots are ready.
- Private core is not included.
- Maintainer explicitly approves publication.

## Protected commercial boundary

The Community candidate workflow does not include the Private Quality Engine, production model router, private evaluation data, speaker-name mapping, commercial templates, or Enterprise modules.
