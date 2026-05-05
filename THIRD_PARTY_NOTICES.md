# Third-party notices

AI Meeting Agent Community uses Python standard library components for much of the public core.

Optional dependencies may be installed for specific workflows:

- `sounddevice` for microphone capture
- `numpy` for audio processing support
- `faster-whisper` for local ASR
- `ctranslate2`, `onnxruntime`, `tokenizers`, `huggingface-hub`, and related packages as transitive ASR dependencies
- `fastapi` and `uvicorn` for optional API serving
- `pytest`, `ruff`, and `mypy` for development workflows

## ASR model notice

Local ASR workflows may download or use third-party speech recognition models. Model weights and datasets can carry separate licenses or usage restrictions.

Before public, commercial, or production use:

- verify the license for any ASR model you download or distribute
- do not redistribute model weights unless the model license allows it
- document the exact model and version used in production-like demos
- review Hugging Face model cards or upstream model licenses before release

## Release checklist

Before any public or commercial distribution:

- run dependency and license scans
- update this notice with exact package versions where needed
- verify that optional ASR model licenses are compatible with the intended use
- confirm no GPL/AGPL code is mixed into private commercial modules unless intentionally licensed
- keep private Quality Engine code and private evaluation datasets outside this repository
