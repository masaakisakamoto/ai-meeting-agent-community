# Real Mac Evidence Collection

v1.9 adds a private evidence collection workflow for the final hardware and launch-review evidence needed before a public alpha announcement.

## Generate the pack

```bash
PYTHONPATH=src python -m meeting_agent real-mac-evidence-pack \
  --out-dir real_mac_evidence_pack
```

This command does **not** open the microphone and does **not** publish anything.

## Collect evidence after live validation

After real microphone capture, post-capture minutes, local ASR smoke, and launch assets are generated, run:

```bash
PYTHONPATH=src python -m meeting_agent real-mac-evidence-collect \
  --root . \
  --evidence-dir real_mac_evidence \
  --mic-dir mic_alpha_live \
  --minutes-dir mic_minutes_live \
  --asr-minutes-dir asr_minutes_faster_whisper \
  --local-asr-dir local_asr_smoke \
  --launch-assets-dir launch_assets
```

The report is expected to remain `warn` until real Mac capture and screenshots are present.

## Publication policy

Publication stays on hold. A maintainer must explicitly change `configs/publication_policy.json` before any public GitHub repository, SNS announcement, public release blog, or commercial landing page launch.
