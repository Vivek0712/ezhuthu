.PHONY: setup data check test lint design-check web-check bench
PY := .venv/bin/python
setup:
	uv venv --python 3.12 .venv && uv pip install --python $(PY) -e ".[dev]"
data:
	$(PY) -m ezhuthu.corpus.fetch
lint:
	.venv/bin/ruff check src tests
test:
	.venv/bin/pytest -q -m "not live and not network"
design-check:
	$(PY) design/tools/check_design.py
check: lint test design-check
web-check:
	cd app/web && npm ci && npm run lint --if-present && npm test --if-present && npm run build
