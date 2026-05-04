# Launch Assets and Desktop Packaging Polish

This document describes the v1.9 private launch asset workflow.

The repository remains private. `publication-gate` must stay on `hold` until the maintainer explicitly changes the publication policy.

## Generate private launch assets

```bash
PYTHONPATH=src python3 -m meeting_agent launch-assets-pack \
  --root . \
  --out-dir launch_assets \
  --demo-dir demo_out
```

This creates private drafts only:

- `QUICKSTART_MACOS.md`
- `KNOWN_LIMITATIONS.md`
- `DEMO_SCRIPT.md`
- `SCREENSHOT_GUIDE.md`
- `GITHUB_RELEASE_DRAFT.md`
- `LAUNCH_CHECKLIST.md`
- `README_PUBLIC_ALPHA_DRAFT.md`
- `launch_asset_manifest.json`

## Check polish

```bash
PYTHONPATH=src python3 -m meeting_agent launch-polish-check \
  --root . \
  --demo-dir demo_out \
  --launch-assets-dir launch_assets
```

## Important

These files are not permission to publish. Public GitHub, SNS, landing page, and public blog announcements remain blocked until:

- real Mac microphone capture evidence passes,
- local ASR smoke evidence passes,
- README and screenshots are final,
- private-core leakage scans pass, and
- the maintainer explicitly flips the publication policy.
