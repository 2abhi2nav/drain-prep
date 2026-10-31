PY ?= .venv/bin/python

.PHONY: install data pipeline test dashboard figures

install:
	python3 -m venv .venv
	$(PY) -m pip install -r requirements.txt

data:
	$(PY) -m drainage_rec.cli download

pipeline:
	$(PY) scripts/run_pipeline.py

figures:
	$(PY) scripts/generate_report_figures.py

test:
	$(PY) -m pytest -q

dashboard:
	$(PY) -m uvicorn drainage_rec.web_api:app --reload
