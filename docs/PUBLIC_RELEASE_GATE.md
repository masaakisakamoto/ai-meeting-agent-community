# Public Release Gate

This document defines the minimum bar before publishing the Community Edition as a public OSS repository.

The goal is not to wait for every feature. The goal is to publish only when the repository is safe, useful, testable, and positioned correctly.

## Release principle

Publish when the project is clearly useful as a Community Edition and clearly separated from the protected commercial Quality Engine.

The first public release should prove these capabilities:

1. Local-first transcript ingestion works.
2. Evidence-linked minutes can be generated from a Japanese meeting sample.
3. Important generated items point back to transcript segments.
4. The repository contains a clean plugin/provider architecture.
5. The public/private boundary is documented.
6. The codebase has tests and a repeatable demo.
7. No private prompts, private datasets, credentials, or commercial-only internals are included.

## Release readiness score

Run:

```bash
PYTHONPATH=src python -m meeting_agent readiness --root . \
  --out-json release_readiness.json \
  --out-md release_readiness.md
```

Recommended public release threshold:

| Gate | Minimum |
|---|---:|
| Readiness status | `pass` |
| Readiness score | `>= 0.92` |
| Unit tests | pass |
| Demo workflow | pass |
| Compile check | pass |
| Private leakage scan | pass |

## Manual checks before public GitHub launch

### Product positioning

- The README clearly says this is a Community Edition prototype.
- The README does not promise production accuracy.
- The roadmap distinguishes Community, Cloud, Team, and Enterprise features.
- The project identity is strong: local-first, evidence-linked, Japanese-first, extensible.

### Code quality

- `python -m compileall -q src tests` passes.
- `python -m unittest discover -s tests -v` passes.
- `meeting-agent demo --out-dir demo_out` produces expected files.
- `meeting-agent readiness --root .` passes.
- No generated `demo_out/` folder is committed unless intentionally included as docs output.

### OSS safety

- License file is present.
- Third-party notices are present.
- Security policy is present.
- Contributor policy is present.
- Trademark guidance is present.
- No GPL/AGPL code has been copied into the permissive Community codebase.
- Any copied MIT/Apache code has notice attribution.

### Protected-core safety

Do not publish:

- Private quality prompts.
- Private Japanese meeting evaluation data.
- Commercial model-routing heuristics.
- Customer or real meeting transcripts.
- Enterprise admin/billing internals.
- Credentials, tokens, or provider keys.
- Non-public integration secrets.

## Recommended first public tag

Use a conservative pre-release tag:

```text
v0.1.0-community-preview
```

Suggested release title:

```text
AI Meeting Agent Community v0.1 — local-first evidence-linked minutes prototype
```

## Do not publish yet if

- The demo fails on a clean machine.
- The README is unclear about prototype limitations.
- The public/private boundary is ambiguous.
- The repository contains private prompts or evaluation data.
- The project has no tests.
- The license strategy is not decided.
