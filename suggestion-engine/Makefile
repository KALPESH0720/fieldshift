PY ?= python

.PHONY: install test run mock schemas lint

install:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest -q

run:
	uvicorn fieldshift.api.main:app --reload

mock:
	cd contracts/mock_server && uvicorn app:app --port 8001

schemas:
	$(PY) -m fieldshift.api.schema_export

lint:
	ruff check src tests
