# OSS compliance checklist

This project can reference and learn from OSS competitors, but it should avoid license contamination.

## Safe references

- Product behavior and UX ideas
- Architecture patterns
- Public docs and README-level feature study
- Clean-room reimplementation
- MIT/Apache code with notices retained

## Avoid

- Copying code from repositories without a license
- Mixing GPL/AGPL code into proprietary/private core
- Copying prompts, docs, or assets verbatim without permission
- Removing third-party notices

## Recommended files

- `LICENSE`
- `NOTICE`
- `THIRD_PARTY_NOTICES.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `TRADEMARK.md`
- SBOM output in release artifacts

## CI recommendations

- Run tests
- Run license scan
- Generate SBOM
- Check that private modules are not imported by OSS package
