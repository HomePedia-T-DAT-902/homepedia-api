.PHONY: help setup install env ingest process load pipeline all api lint format pre-commit test ci clean

help: ## Afficher cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Setup ────────────────────────────────────────────────────────────

env: ## Créer .env depuis .env.example (si absent)
	cp -n .env.example .env || true

setup: env ## Setup complet (env + deps + services db/spark)
	poetry install
	docker compose up -d db spark-master spark-worker-1 spark-worker-2

install: ## Installer les dépendances + hooks pre-commit
	pip install poetry
	poetry install --no-root
	poetry run pre-commit install

# ─── Pipeline de données ─────────────────────────────────────────────

ingest: ## Télécharger les données brutes (toutes les sources)
	docker compose run --rm processing python -m src.pipeline download

process: ## Traiter via PySpark (toutes les sources)
	docker compose run --rm processing python -m src.pipeline process

load: ## Charger en base PostgreSQL (toutes les sources)
	docker compose run --rm processing python -m src.pipeline load

pipeline: ## Pipeline complet (download + preprocess + process + load)
	docker compose run --rm processing python -m src.pipeline run-all

all: env ## Tout lancer d'un coup (services + pipeline complet + API)
	docker compose up -d
	$(MAKE) pipeline
	docker compose up -d api

# ─── API ──────────────────────────────────────────────────────────────

api: ## Lancer l'API en local (hot reload, hors Docker)
	poetry run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# ─── Qualité du code ─────────────────────────────────────────────────

lint: ## Lancer le linter (ruff check)
	poetry run ruff check src/ tests/

format: ## Formater le code (ruff format)
	poetry run ruff format src/ tests/

pre-commit: ## Lancer tous les hooks pre-commit sur le repo
	poetry run pre-commit run --all-files

# ─── Tests ────────────────────────────────────────────────────────────

test: ## Lancer les tests (pytest)
	poetry run pytest tests/ -v --tb=short

ci: lint test ## Rejouer les checks CI en local (lint + tests)
	@echo "\n✅ Tous les checks passent"

# ─── Nettoyage ────────────────────────────────────────────────────────

clean: ## Nettoyer containers + volumes + fichiers temporaires
	docker compose down -v
	rm -rf data/raw/* data/processed/*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
