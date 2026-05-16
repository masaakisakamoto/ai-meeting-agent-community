# ASR Model Recommendations

## Current benchmark

This benchmark used a short real-microphone Japanese Public Alpha smoke sample.

The audio and generated ASR artifacts are local-only and must not be committed.

## Results

| Model | Normalized JA CER | CER | WER | Runtime | Notes |
|---|---:|---:|---:|---:|---|
| faster-whisper small | 0.4078 | 0.3874 | 1.0 | 5.444s | Fast, but weak for Japanese accuracy |
| faster-whisper medium | 0.2330 | 0.2342 | 0.75 | 156.041s | Good balanced profile |
| faster-whisper turbo | 0.2816 | 0.3243 | 1.0 | 156.660s | Not best on this sample |
| faster-whisper large-v3 | 0.2136 | 0.2252 | 0.75 | 303.105s | Best current local profile |
| JhonVanced/faster-whisper-large-v3-ja | 0.2816 | 0.2793 | 1.0 | 312.166s | Experimental; did not beat large-v3 on this sample |

## Recommendation

For Public Alpha:

- Use `small` only for smoke tests.
- Use `medium` as the balanced CPU-only local ASR profile.
- Use `large-v3` when accuracy matters more than runtime.
- Re-test Japanese fine-tuned models on a larger dataset before recommending them.

## World-class accuracy path

Model choice alone is not enough.

Next layers:

1. Japanese-aware text normalization
2. Domain glossary correction
3. Multi-model / multi-pass comparison
4. ASR confidence and evidence display
5. Human review UI
6. Private Quality Engine for production-grade Japanese correction

## Current decision

This repository should continue to describe ASR as Public Alpha local validation.

Do not claim production-grade transcription accuracy yet.
