# Quality Bar

The project is designed around measurable quality rather than vague claims.

## Core quality principles

1. **Evidence-first output**: decisions, ToDos, risks, and open questions must link back to transcript segments.
2. **Separation of draft and final**: realtime output is provisional; post-meeting output is verified.
3. **Provider independence**: ASR, LLM, export, storage, and integration providers must remain swappable.
4. **Private moat protection**: commercial-quality orchestration and evaluation assets stay outside the public repository.
5. **Release gates before announcements**: public releases must pass deterministic checks.

## Minimum Community quality gates

| Area | Gate |
|---|---|
| Transcript | Timestamped segments are preserved. |
| Minutes | Generated items carry evidence segment IDs. |
| Verification | High-severity ungrounded items fail the gate. |
| Security | Secret scan returns pass. |
| OSS hygiene | License, notice, security, contribution, and boundary docs exist. |
| Tests | Unit tests and compile checks pass. |

## Commercial Quality Engine targets

These are intentionally not implemented in the public core, but they define the direction.

| Capability | Target |
|---|---|
| Japanese correction | Company, product, person, and domain terms normalized with audit trail. |
| Model router | Select ASR/LLM providers by quality, latency, cost, privacy, and tenant policy. |
| Verifier pipeline | Cross-check generated claims against transcript evidence and flag weak grounding. |
| Speaker intelligence | Map speaker labels to participants with explicit confidence and correction workflow. |
| Evaluation | Maintain private Japanese meeting datasets and regression tests. |
| Enterprise trust | Audit logs, retention controls, admin policy, and permission boundaries. |

## Publication language

Allowed:

- "Developer preview"
- "Community prototype"
- "Evidence-linked meeting minutes baseline"
- "Open-core-ready architecture"

Avoid until product gates pass:

- "Production-ready"
- "Enterprise-ready"
- "World-best transcription"
- "Fully realtime meeting assistant"
