# Audio Quality Diagnostics

v0.5 adds deterministic WAV diagnostics so a meeting can be checked before spending ASR or LLM compute.

## Command

```bash
meeting-agent audio-quality ./audio.wav --out ./audio_quality.json
```

## Metrics

| Metric | Meaning |
|---|---|
| `duration_ms` | Audio length. Very short files are unreliable for transcription tests. |
| `rms_dbfs` | Average level. Low values indicate quiet audio; very high values indicate overload risk. |
| `peak_dbfs` | Highest observed level. Near 0 dBFS may indicate clipping. |
| `silence_ratio` | Fraction of samples near silence. |
| `clipping_ratio` | Fraction of samples near the PCM limit. |
| `score` | Lightweight deterministic score for release/demo gates. |

## Interpretation

- `pass`: suitable for controlled test transcription.
- `warn`: usable, but user should review gain/device/route.
- `fail`: likely broken for reliable transcription.

This is not a replacement for production acoustic scoring. It is an OSS-safe baseline that catches common failures early.
