# Security Threat Model

This is a lightweight threat model for the Community Edition and future commercial versions.

## Assets

| Asset | Why it matters |
|---|---|
| Meeting audio | Highly sensitive, may contain business or personal data |
| Transcript segments | Searchable text version of sensitive conversation |
| Generated minutes | Can encode decisions, risks, tasks, names, and deadlines |
| Evidence links | Connect generated claims to source conversation |
| Provider credentials | Can be abused for API cost and data access |
| Plugin execution path | May access local files or external systems |
| Private Quality Engine | Commercial differentiation and quality moat |

## Trust boundaries

```text
User device
  ├─ local audio capture
  ├─ local transcript store
  ├─ local plugins
  └─ optional provider credentials

Optional cloud services
  ├─ ASR provider
  ├─ LLM provider
  ├─ hosted Quality Engine
  └─ team workspace / integrations
```

## Main threats and controls

| Threat | Control |
|---|---|
| Accidental publication of private meeting data | `.gitignore`, docs warnings, redaction command, release scan |
| Credential leak | Do not store provider keys in repo; scan obvious secret patterns |
| Hallucinated decisions or tasks | Evidence links, verifier, human review workflow |
| Plugin abuse | Plugin manifest, capability model, future sandboxing |
| Vendor lock-in | Provider interfaces and local-first mode |
| Commercial-core leakage | Separate repository, no private prompts/datasets in public repo |
| User confusion about accuracy | Prototype status, verifier status, candidate item status |
| Unwanted data retention | Local-first default and future retention policy controls |

## Community Edition security posture

The Community Edition should default to local operation and should avoid sending audio or transcript data to external providers unless the user explicitly configures a provider.

## Future commercial security controls

- Workspace RBAC.
- Audit logs.
- SSO/SAML/OIDC.
- Data retention policy.
- DLP/PII redaction.
- Tenant isolation.
- KMS-managed encryption.
- Admin export/delete workflows.
- Plugin permissions.
- Provider usage logging.

## Security non-goals for v0.1

- Full desktop audio sandboxing.
- Enterprise-grade plugin isolation.
- Cloud tenant isolation.
- Formal penetration test.
- Compliance certification.

Those are future commercial or enterprise milestones.
