PYTHON ?= $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)

.PHONY: download ingest sprint0

download:
	$(PYTHON) -m src.ingest.download_wer

ingest:
	$(PYTHON) -m scripts.sprint1_ingest_bronze

sprint0:
	$(PYTHON) -m scripts.sprint0_walking_skeleton
