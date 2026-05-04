# Plugin System

The Community Edition is designed to be extended through provider and plugin boundaries instead of hardcoding every feature into the core.

## Goals

- Add many features without making the core unstable.
- Allow OSS contributors to build exporters, templates, providers, and integrations.
- Keep the protected commercial Quality Engine separate.
- Make model/provider upgrades easy.

## Plugin categories

| Category | Examples | Public by default? |
|---|---|---|
| ASR provider | faster-whisper, whisper.cpp, OpenAI-compatible ASR | Yes |
| LLM provider | Ollama, LM Studio, OpenAI-compatible endpoint | Yes |
| Exporter | Markdown, JSON, Obsidian, DOCX, PDF | Yes |
| Template | engineering, sales, recruiting, 1on1 | Basic yes; advanced optional |
| Integration | Slack, Notion, Jira, Linear, Google Docs | Basic yes; team workflows commercial |
| Verifier | grounding checker, hallucination checker | Basic yes; advanced commercial |
| Compliance | redaction, consent log, retention policy | Basic yes; enterprise commercial |

## Current extension points

- `ASRProvider`
- `LLMProvider`
- `RuleBasedMinutesGenerator.generate(...)`
- `MinutesVerifier.verify(...)`
- `MarkdownExporter.export(...)`
- `PluginRegistry`

## Design rule

The Community app should call interfaces. It should not know whether the implementation is:

- local;
- BYOK;
- cloud-hosted;
- open-source;
- commercial;
- experimental.

## Plugin metadata

Recommended plugin metadata:

```json
{
  "id": "obsidian-export",
  "kind": "exporter",
  "name": "Obsidian Markdown Export",
  "version": "0.1.0",
  "capabilities": ["markdown", "local-file"],
  "permissions": ["write-local-file"],
  "license": "Apache-2.0"
}
```

## Future plugin permission model

For desktop and cloud safety, plugins should eventually declare capabilities:

- `read-transcript`
- `write-local-file`
- `network-access`
- `create-task`
- `publish-message`
- `read-calendar`
- `write-calendar`

The app should display these capabilities before enabling a plugin.
