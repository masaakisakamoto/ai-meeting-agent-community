# Private core boundaries

This repository is the public Community Edition. It should expose the product shell, schemas, baseline algorithms, plugin/provider interfaces, and safe examples. The commercial moat should live in a separate protected repository or hosted service.

## Keep these assets out of the public repository

1. **Quality Engine** implementation for high-accuracy Japanese meeting understanding.
2. Private prompts and orchestration graphs.
3. Japanese correction and term normalization rules beyond safe examples.
4. Advanced **Verifier** scoring logic beyond the basic public baseline.
5. **Model Router** heuristics, cost optimizer, and provider selection policy.
6. Private meeting **evaluation** datasets and regression suites.
7. Speaker identification embeddings and mapping heuristics.
8. Enterprise admin, billing, audit, and compliance modules.
9. Hosted infrastructure code if it exposes sensitive operational details.

## Public repository responsibilities

The public package should define interfaces that private modules can implement:

- ASR provider interface.
- LLM provider interface.
- Minutes generator boundary.
- Verifier boundary.
- Exporter/plugin boundary.
- Release readiness and quality gates.

## Safe public examples

The Community Edition can include synthetic Japanese samples, baseline extraction rules, and lightweight quality gates. It should not include real meeting content, customer-specific terminology, private prompts, or private benchmark data.

## Commercial integration pattern

```text
Community App / CLI / SDK
  -> public interfaces
  -> protected hosted Quality Engine or private module
  -> advanced verification, Japanese correction, model routing, enterprise workflow
```

This boundary allows the Community Edition to be useful and extensible while preserving the parts that create commercial defensibility.
