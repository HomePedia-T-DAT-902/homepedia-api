.PHONY: help setup install ingest process load api update all lint format typecheck test ci spec spec-check clean

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
