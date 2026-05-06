# Pull Request Checklist

## Safety

- [ ] This PR does not commit raw audio, private transcripts, customer data, credentials, or generated evidence directories.
- [ ] This PR does not include private Quality Engine code or private evaluation datasets.
- [ ] This PR does not weaken `publication-gate`.
- [ ] This PR does not change `configs/publication_policy.json` unless it is an explicit maintainer-approved public unlock PR.

## Release / publication

- [ ] `release-check` passes.
- [ ] `publication-gate` remains HOLD unless this is the final approved unlock.
- [ ] CI passes.
- [ ] README / SECURITY / PRIVACY changes do not overclaim production readiness.

## Notes

This repository is a Public Alpha Candidate while publication remains intentionally blocked.
