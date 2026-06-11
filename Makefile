.PHONY: help setup install ingest process load api update all lint format typecheck test ci spec spec-check clean \
	load-geo load-dvf load-dpe load-bpe load-trends \
	process-dvf process-dpe process-bpe \
	pipeline-dvf pipeline-dpe pipeline-bpe \
	test-pipelines db-reset

help: ## Afficher cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Setup ────────────────────────────────────────────────────────────

setup: ## Setup complet (env + deps + containers)
	cp -n .env.example .env || true
	poetry install
	docker compose up -d db spark-master spark-worker-1 spark-worker-2

install: ## Installer les dépendances + pre-commit
	pip install poetry
	poetry install --no-root
	pip install pre-commit
	pre-commit install

# ─── Pipeline de données ─────────────────────────────────────────────

ingest: ## Télécharger les données brutes
	docker compose run --rm processing python -m src.ingestion.download_geo
	docker compose run --rm processing python -m src.ingestion.download_dvf
	docker compose run --rm processing python -m src.ingestion.download_dpe
	docker compose run --rm processing python -m src.ingestion.download_bpe
	docker compose run --rm processing python -m src.ingestion.download_insee
	docker compose run --rm processing python -m src.ingestion.download_loyers
	docker compose run --rm processing python -m src.ingestion.download_crime
	docker compose run --rm processing python -m src.ingestion.download_education
	docker compose run --rm processing python -m src.ingestion.download_iris

process: ## Traiter via PySpark
	docker compose run --rm processing python -m src.processing.spark_dvf
	docker compose run --rm processing python -m src.processing.spark_dpe
	docker compose run --rm processing python -m src.processing.spark_aggregations
	docker compose run --rm processing python -m src.processing.spark_reviews

load: ## Charger en base PostgreSQL
	docker compose run --rm processing python -m src.database.postgres_loader

# ─── Chargement individuel (dev) ──────────────────────────────────────

load-geo: ## Charger uniquement les communes/régions/depts (prérequis FK)
	docker compose run --rm processing python -m src.database.postgres_loader \
		--skip-dvf --skip-dpe --skip-bpe --skip-trends --skip-cadastre

load-dvf: ## Charger uniquement DVF (requiert load-geo)
	docker compose run --rm processing python -m src.database.postgres_loader \
		--skip-geo --skip-dpe --skip-bpe --skip-cadastre

load-dpe: ## Charger uniquement DPE (requiert load-geo)
	docker compose run --rm processing python -m src.database.postgres_loader \
		--skip-geo --skip-dvf --skip-bpe --skip-trends --skip-cadastre

load-bpe: ## Charger uniquement BPE (requiert load-geo)
	docker compose run --rm processing python -m src.database.postgres_loader \
		--skip-geo --skip-dvf --skip-dpe --skip-trends --skip-cadastre

load-trends: ## Calculer et charger les price_trends uniquement
	docker compose run --rm processing python -m src.database.postgres_loader \
		--skip-geo --skip-dvf --skip-dpe --skip-bpe --skip-cadastre

# ─── Processing individuel (dev) ──────────────────────────────────────

process-dvf: ## Processing Spark DVF uniquement
	docker compose run --rm processing python -m src.processing.spark_dvf

process-dpe: ## Processing Spark DPE uniquement
	docker compose run --rm processing python -m src.processing.spark_dpe

process-bpe: ## Processing Spark BPE uniquement
	docker compose run --rm processing python -m src.processing.spark_bpe

# ─── Pipelines individuels bout-en-bout (dev) ─────────────────────────

pipeline-dvf: process-dvf load-dvf ## DVF : processing Spark + chargement BDD

pipeline-dpe: process-dpe load-dpe ## DPE : processing Spark + chargement BDD

pipeline-bpe: process-bpe load-bpe ## BPE : processing Spark + chargement BDD

# ─── Tests + reset (dev) ──────────────────────────────────────────────

test-pipelines: ## Tests des pipelines data lourds (DVF, DPE, BPE)
	poetry run pytest tests/processing/test_spark_dpe.py tests/processing/test_spark_bpe.py \
		tests/ingestion/test_download_dvf.py tests/ingestion/test_download_bpe.py -v --tb=short

db-reset: ## Vider et réinitialiser la base (DROP + recréation du schéma)
	docker compose run --rm processing python -c \
		"from src.database.postgres_loader import get_connection, init_schema; \
		conn = get_connection(); \
		conn.cursor().execute('DROP SCHEMA public CASCADE; CREATE SCHEMA public;'); \
		conn.commit(); \
		init_schema(conn); \
		conn.close(); \
		print('BDD réinitialisée')"

update: ## Mise à jour incrémentale (7 derniers jours)
	poetry run python -m src.ingestion.update_all --since $$(date -v-7d +%Y-%m-%d)

all: ## Pipeline complet (services + ingestion + processing + chargement + API)
	docker compose up -d
	$(MAKE) ingest
	$(MAKE) process
	$(MAKE) load
	docker compose up -d api

# ─── API ──────────────────────────────────────────────────────────────

api: ## Lancer l'API en local (hot reload)
	poetry run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# ─── Qualité du code ─────────────────────────────────────────────────

lint: ## Lancer le linter (ruff)
	poetry run ruff check src/

format: ## Formater le code (ruff)
	poetry run ruff format src/

typecheck: ## Vérifier les types (mypy)
	poetry run mypy src/api/ --ignore-missing-imports

# ─── Tests ────────────────────────────────────────────────────────────

test: ## Lancer les tests (pytest)
	poetry run pytest tests/ -v --tb=short

member-c-test: ## Tests ciblés pipeline Membre C
	python -m src.pipeline.member_c test --unit

member-c-integration: ## Test d'intégration PostgreSQL pipeline Membre C
	python -m src.pipeline.member_c test --integration

member-c-ingest: ## Ingestion pipeline Membre C
	python -m src.pipeline.member_c ingest

member-c-process: ## Processing Spark pipeline Membre C
	python -m src.pipeline.member_c process

member-c-load: ## Chargement PostgreSQL pipeline Membre C
	python -m src.pipeline.member_c load

member-c-all: ## Pipeline complète Membre C
	python -m src.pipeline.member_c all

ci: lint typecheck test ## Lancer tous les checks CI en local
	@echo "\n✅ Tous les checks passent"

# ─── Contrat API ──────────────────────────────────────────────────────

spec: ## Générer openapi.json depuis FastAPI
	python scripts/export_openapi.py

spec-check: spec ## Vérifier que openapi.json est à jour
	@git diff --exit-code openapi.json || (echo "\n❌ openapi.json n'est pas à jour. Committez le fichier." && exit 1)
	@echo "✅ openapi.json est à jour"

# ─── Nettoyage ────────────────────────────────────────────────────────

clean: ## Nettoyer fichiers temporaires + containers
	docker compose down -v
	rm -rf data/raw/* data/processed/*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
