# OSS Release Criteria

## Developer preview can be public when

- Unit tests pass on a clean checkout.
- `meeting-agent demo` generates transcript, minutes, verification, quality, and UI outputs.
- README clearly says real audio capture and heavyweight ASR are extension points.
- Private core boundaries are documented.
- Secret scan and release-check pass.

## Broad Community product release should wait until

- Native audio capture works on at least one platform with clear permissions UX.
- Local ASR setup is documented and tested.
- Desktop UI supports real start/stop recording state.
- Consent notice is visible in the app UX.
- Export workflows are clickable from the app.
- Installation is one-command or packaged.

## Never include in the public Community repo

- private Quality Engine code
- model router policies
- private evaluation datasets
- customer data
- production credentials
- commercial-only templates or integrations
