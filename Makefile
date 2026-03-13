.PHONY: setup ingest process load api update all clean

# ── Setup ──
setup:
	cp -n .env.example .env || true
	poetry install
	docker compose up -d db spark-master spark-worker-1 spark-worker-2

# ── Ingestion des données brutes ──
ingest:
	poetry run python -m src.ingestion.download_geo
	poetry run python -m src.ingestion.download_dvf
	poetry run python -m src.ingestion.download_dpe
	poetry run python -m src.ingestion.download_bpe
	poetry run python -m src.ingestion.download_insee
	poetry run python -m src.ingestion.download_loyers
	poetry run python -m src.ingestion.download_crime
	poetry run python -m src.ingestion.download_education

# ── Traitement PySpark ──
process:
	poetry run python -m src.processing.spark_dvf
	poetry run python -m src.processing.spark_dpe
	poetry run python -m src.processing.spark_aggregations
	poetry run python -m src.processing.spark_reviews

# ── Chargement en base ──
load:
	poetry run python -m src.database.postgres_loader

# ── Lancement API ──
api:
	poetry run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# ── Mise à jour incrémentale ──
update:
	poetry run python -m src.ingestion.update_all --since $$(date -v-7d +%Y-%m-%d)

# ── Pipeline complet ──
all: setup ingest process load api

# ── Nettoyage ──
clean:
	docker compose down -v
	rm -rf data/raw/* data/processed/*
