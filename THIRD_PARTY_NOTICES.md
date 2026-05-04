# Third-party notices

AI Meeting Agent Community uses Python standard library components for much of the public core.

Optional dependencies may be installed for specific workflows:

- `sounddevice` for microphone capture
- `numpy` for audio processing support
- `faster-whisper` for local ASR
- `ctranslate2`, `onnxruntime`, `tokenizers`, `huggingface-hub`, and related packages as transitive ASR dependencies
- `fastapi` and `uvicorn` for optional API serving
- `pytest`, `ruff`, and `mypy` for development workflows

Before any public or commercial distribution:

- run dependency and license scans
- update this notice with exact package versions
- verify that optional ASR model licenses are compatible with the intended use
- confirm no GPL/AGPL code is mixed into private commercial modules unless intentionally licensed
- keep private Quality Engine code and private evaluation datasets outside this repository
