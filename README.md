# Homepedia API

Backend de la plateforme d'analyse du marché immobilier français (Projet Epitech T-DAT-902).

## Stack

- **API** : FastAPI (async, Pydantic v2)
- **BDD** : PostgreSQL 16 + PostGIS 3.4
- **Big Data** : PySpark 3.5
- **Scraping** : Scrapy, BeautifulSoup

## Prérequis

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)
- Docker & Docker Compose

## Installation

```bash
# Cloner le repo
git clone git@github.com:<org>/homepedia-api.git
cd homepedia-api

# Setup (copie .env, installe les deps, lance les conteneurs)
make setup
```

## Lancement

```bash
# Lancer l'API en mode dev (hot reload)
make api

# Ou via Docker Compose (tout-en-un)
docker compose up -d
```

L'API est disponible sur `http://localhost:8000`.
Documentation Swagger : `http://localhost:8000/docs`.

## Pipeline de données

```bash
# 1. Télécharger les données brutes
make ingest

# 2. Traiter via PySpark
make process

# 3. Charger en base PostgreSQL
make load

# Pipeline complet
make all
```

## Architecture

```
src/
  ingestion/     # Scripts de téléchargement (1 par source)
  scraping/      # Web scrapers (ville-ideale.fr, pap.fr)
  processing/    # Jobs PySpark
  database/      # Schéma SQL, loaders PostgreSQL
  api/           # FastAPI (routers: communes, prices, stats, geo, reviews)
data/raw/        # Fichiers bruts (non versionnés)
data/processed/  # Sorties Parquet (non versionnées)
tests/           # Tests unitaires et d'intégration
```

## Tests

```bash
poetry run pytest
```

## Pipeline Membre C

Commande unique pour la pipeline lourde DVF/DPE/BPE/cadastre :

```bash
# Tests ciblés ingestion + Spark + BPE
python -m src.pipeline.member_c test --unit

# Test d'intégration PostgreSQL
python -m src.pipeline.member_c test --integration

# Pipeline complète
python -m src.pipeline.member_c all

# Variante avec cadastre limité à quelques départements
python -m src.pipeline.member_c all --with-cadastre --cadastre-dept 75 13
```

Sur Windows, si vous utilisez le venv local du repo :

```powershell
.\.venv\Scripts\python.exe -m src.pipeline.member_c test --unit
```

## Documentation

Voir le dossier [docs/](docs/) pour la documentation détaillée :

- [Cahier des charges](docs/project.md)
- [Architecture](docs/architecture.md)
- [Sources de données](docs/datagouv-digest.md)
- [Schéma BDD](docs/database.md)
- [Contrat API](docs/api-contrat.md)
