# Maintainer Evidence Dashboard

`v2.1` adds a private maintainer dashboard for deciding whether the project is ready for Public Alpha.

The dashboard intentionally does **not** publish anything and does **not** open the microphone. It combines:

- publication-gate
- release-check
- public-alpha-readiness
- public-alpha-candidate-gate
- real Mac evidence collection
- launch assets gate
- screenshot count
- private-core leakage guard

## Generate the review pack

```bash
PYTHONPATH=src python -m meeting_agent maintainer-review-pack --out-dir maintainer_review
```

## Build the dashboard

```bash
PYTHONPATH=src python -m meeting_agent maintainer-dashboard --root . --dashboard-dir maintainer_dashboard
open maintainer_dashboard/maintainer_dashboard.html
```

## Publication policy

The dashboard can show that a candidate is close, but public release remains blocked until `configs/publication_policy.json` is explicitly unlocked by the maintainer after real Mac evidence, local ASR smoke, screenshots, and launch materials are reviewed.
