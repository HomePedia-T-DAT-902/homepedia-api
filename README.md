# Homepedia API

Backend de la plateforme d'analyse du marché immobilier français (Projet Epitech T-DAT-902).

## Stack

- **API** : FastAPI (async, Pydantic v2)
- **BDD** : PostgreSQL 16 + PostGIS 3.4
- **Big Data** : PySpark 3.5
- **Pipeline** : orchestrateur CLI `src/pipeline.py`

## Prérequis

- Docker Desktop
- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)

## Démarrage rapide

```bash
# 1. Cloner le repo
git clone git@github.com:HomePedia-T-DAT-902/homepedia-api.git
cd homepedia-api

# 2. Installer les dépendances Python
poetry install

# 3. Lancer les services (PostgreSQL + PostGIS + Spark)
docker-compose up -d
```

> Le schéma SQL (tables + index + PostGIS) est créé **automatiquement** au premier démarrage via `docker-entrypoint-initdb.d`.

L'API est disponible sur `http://localhost:8000`.
Documentation Swagger : `http://localhost:8000/docs`.

## Pipeline de données

Le pipeline tourne dans le container Docker `processing`. Il est piloté par une interface CLI unique :

```bash
# Pipeline complet (toutes les sources)
docker compose run --rm processing python -m src.pipeline run-all

# Sources spécifiques uniquement
docker compose run --rm processing python -m src.pipeline run --sources geo bpe

# Tout sauf certaines sources (ex: DVF et DPE sont volumineux)
docker compose run --rm processing python -m src.pipeline run-all --skip dvf dpe

# Relancer sans re-télécharger (données raw déjà présentes)
docker compose run --rm processing python -m src.pipeline run --sources bpe --skip-download

# Étapes individuelles
docker compose run --rm processing python -m src.pipeline download --sources geo
docker compose run --rm processing python -m src.pipeline preprocess --sources bpe
docker compose run --rm processing python -m src.pipeline process --sources geo bpe
docker compose run --rm processing python -m src.pipeline load --sources geo bpe
```

### Sources disponibles

| Source | Description | Volume |
|--------|-------------|--------|
| `geo` | Communes, départements, régions (Etalab) | ~35k communes |
| `bpe` | Équipements par commune (INSEE) | ~2.8M lignes |
| `dvf` | Transactions immobilières 2020-2024 (DGFiP) | ~10M lignes |
| `dpe` | Diagnostics de performance énergétique (ADEME) | ~24M lignes |
| `iris` | Contours IRIS infra-communaux (IGN) | ~49k polygones |
| `cadastre` | Parcelles cadastrales (Etalab) | ~70M parcelles |

> **Note** : DVF, DPE et cadastre représentent plusieurs dizaines de GB. Prévoir le téléchargement en conséquence.

## Architecture

```
src/
  sources/           # Une source = un dossier autonome
    base.py          # Interface DataSource (ABC) : download / preprocess / process / load
    utils.py         # Utilitaires HTTP partagés
    geo/             # Données géographiques (communes, depts, régions)
    bpe/             # Équipements (Base Permanente des Équipements)
    dvf/             # Demandes de Valeurs Foncières
    dpe/             # Diagnostics de Performance Énergétique
    iris/            # Contours IRIS (quartiers infra-communaux)
    cadastre/        # Parcelles cadastrales
  processing/
    spark_utils.py   # Helper SparkSession partagé
  database/
    postgres_schema.sql  # Schéma SQL (exécuté automatiquement par Docker)
  api/               # FastAPI (routers: communes, geo)
  pipeline.py        # Orchestrateur CLI

data/raw/            # Fichiers bruts téléchargés (non versionnés)
data/processed/      # Fichiers Parquet produits par Spark (non versionnés)
tests/               # Tests unitaires et d'intégration
```

### Interface DataSource

Chaque source implémente 4 étapes obligatoires :

```python
class MaSource(DataSource):
    def download(self)    -> None: ...  # Télécharge les fichiers bruts
    def preprocess(self)  -> None: ...  # Valide les fichiers avant Spark
    def process(self)     -> None: ...  # Job Spark → Parquet
    def load(self)        -> None: ...  # Parquet → PostgreSQL
```

## Tests

```bash
poetry run pytest
```

## Documentation

Voir le dossier [docs/](docs/) pour la documentation détaillée :

- [Cahier des charges](docs/project.md)
- [Architecture](docs/architecture.md)
- [Sources de données](docs/datagouv-digest.md)
- [Schéma BDD](docs/database.md)
- [Contrat API](docs/api-contrat.md)
