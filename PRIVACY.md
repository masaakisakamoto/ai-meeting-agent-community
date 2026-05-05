# Privacy notes

AI Meeting Agent Community is designed as a local-first Public Alpha Candidate.

## Current behavior

The Community workflows can process local transcripts, generated WAV files, sidecar transcripts, and evidence-linked minutes.

Raw microphone recordings and meeting transcripts may contain sensitive personal or business information.

## Do not commit sensitive data

Do not commit:

- raw audio recordings
- private meeting transcripts
- customer or participant information
- API keys or credentials
- generated evidence bundles containing real meeting data

Generated local artifacts should stay local unless intentionally reviewed and sanitized.

## Recording consent

Do not record meetings without notifying participants and obtaining appropriate consent for your jurisdiction and use case.

## Public repository policy

The public Community repository should contain source code, examples, documentation, and safe deterministic demo data only.

It should not contain private meeting audio, private transcripts, private evaluation datasets, or private Quality Engine code.
