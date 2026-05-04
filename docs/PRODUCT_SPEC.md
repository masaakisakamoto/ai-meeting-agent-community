# Product Spec: AI Meeting Agent Community

## Product thesis

Build a local-first, evidence-linked AI meeting agent that can start as a useful OSS portfolio project and later grow into a commercial Meeting Intelligence Platform.

## User promise

The user can turn meeting transcripts into structured minutes with decisions, action items, open questions, risks, and evidence links.

## Community Edition value

- Runs locally.
- Uses open interfaces.
- Produces evidence-linked output.
- Can be extended through plugins.
- Demonstrates high-quality architecture without exposing the commercial Quality Engine.

## Non-goals for v0.1

- Perfect transcription accuracy.
- Production-grade live audio capture.
- Fully automatic speaker identification.
- Enterprise workspace administration.
- One-click SaaS onboarding.

## v0.1 user flows

### Flow 1: ingest a transcript

```bash
meeting-agent ingest examples/sample_meeting_ja.txt --out meeting.json
```

### Flow 2: generate minutes

```bash
meeting-agent minutes meeting.json --out-json minutes.json --out-md minutes.md
```

### Flow 3: verify grounding

```bash
meeting-agent verify meeting.json minutes.json --out verification.json
```

### Flow 4: check release readiness

```bash
meeting-agent readiness --root . --out-md release_readiness.md
```

## v0.2 target

- Stronger Japanese action-item extraction.
- Template-driven minutes output.
- Better evidence rendering.
- Local ASR integration guide.
- Optional desktop shell prototype.
- Plugin manifest loading.

## v0.3 target

- Live transcript buffer.
- Desktop audio capture prototype.
- Obsidian/Notion/Slack plugins.
- Basic term dictionary.
- Human review workflow.

## Commercial direction

The commercial edition should sell quality, reliability, and team operations rather than basic transcription.

Commercial candidates:

- High-accuracy Japanese Quality Engine.
- Advanced verifier pipeline.
- Model router.
- Speaker-name mapping.
- Team workspace.
- Enterprise audit logs.
- External workflow automation.
