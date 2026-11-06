PY ?= python

.PHONY: install test run mock schemas lint compile p1-local

install:
	$(PY) -m pip install -e ".[dev,data,pipelines]"

test:
	$(PY) -m pytest -q

run:
	uvicorn fieldshift.api.main:app --reload

mock:
	cd contracts/mock_server && uvicorn app:app --port 8001

schemas:
	$(PY) -m fieldshift.api.schema_export

lint:
	ruff check src tests pipelines scripts

compile:
	$(PY) -m pipelines.compile

p1-local:
	$(PY) scripts/run_p1_local.py --region pune_demo --source synthetic --layer-version dev1
