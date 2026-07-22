.PHONY: download ingest sprint0

download:
	python -m src.ingest.download_wer

ingest:
	python -m scripts.sprint1_ingest_bronze

sprint0:
	python -m scripts.sprint0_walking_skeleton
