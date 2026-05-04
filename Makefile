.PHONY: test demo readiness compile clean

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

compile:
	PYTHONPATH=src python -m compileall -q src tests

demo:
	PYTHONPATH=src python -m meeting_agent demo --out-dir demo_out

readiness:
	PYTHONPATH=src python -m meeting_agent readiness --root . --out-json release_readiness.json --out-md release_readiness.md

clean:
	rm -rf demo_out release_readiness.json release_readiness.md __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
