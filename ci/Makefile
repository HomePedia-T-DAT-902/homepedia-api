.PHONY: help install lint format typecheck test contract-test spec spec-check serve clean

help: ## Afficher cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Setup ────────────────────────────────────────────────────────────

install: ## Installer les dépendances
	pip install poetry
	poetry install --no-root
	pip install pre-commit
	pre-commit install

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

contract-test: serve ## Lancer les tests de conformité API (schemathesis)
	st run http://localhost:8000/openapi.json --checks all --hypothesis-max-examples 20

# ─── Contrat API ──────────────────────────────────────────────────────

spec: ## Générer openapi.json depuis FastAPI
	python scripts/export_openapi.py

spec-check: spec ## Vérifier que openapi.json est à jour
	@git diff --exit-code openapi.json || (echo "\n❌ openapi.json n'est pas à jour. Committez le fichier." && exit 1)
	@echo "✅ openapi.json est à jour"

spec-lint: ## Lint du schéma OpenAPI (Spectral)
	npx @stoplight/spectral-cli lint openapi.json --ruleset .spectral.yml

# ─── Serveur ──────────────────────────────────────────────────────────

serve: ## Lancer l'API en local
	poetry run uvicorn src.api.main:app --reload --port 8000

# ─── Raccourcis ───────────────────────────────────────────────────────

ci: lint typecheck test spec-check ## Lancer tous les checks CI en local
	@echo "\n✅ Tous les checks passent"

clean: ## Nettoyer les fichiers temporaires
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
