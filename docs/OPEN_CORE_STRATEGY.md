# Open-core strategy

## Goal

Ship a useful OSS product early while keeping the highest-value quality logic protected.

## Public OSS

- Transcript ingestion
- Basic local ASR integration points
- Basic rule-based minutes generation
- Evidence data model
- Markdown export
- Plugin SDK
- Public benchmark runner
- Docs and architecture

## Private / commercial

- High-accuracy Japanese meeting generator
- LLM prompt chains and verifier logic
- Model router and cost optimizer
- Speaker-name mapping
- Domain dictionary engine
- Private evaluation datasets
- Team workspace
- Enterprise admin, SSO, audit log, billing
- Advanced integrations

## Pricing compatibility

The OSS version sells trust and community. The hosted version sells:

- setup-free usage
- higher quality
- speed
- team sharing
- integrations
- compliance
- support

## Code theft mitigation

- Do not publish the private quality engine.
- Keep commercial modules in a separate repository.
- Put server-side quality APIs behind authentication and rate limits.
- Use Apache-2.0/MIT only for public shell unless another license is intentional.
- Avoid copying GPL/AGPL code into private modules.
- Track dependencies with `THIRD_PARTY_NOTICES.md` and SBOM tooling.
