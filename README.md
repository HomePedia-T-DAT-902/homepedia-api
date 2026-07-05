# Homepedia API

Backend de la plateforme d'analyse du marché immobilier français (Projet Epitech T-DAT-902).

Collecte, traitement (PySpark) et exposition (FastAPI) de données immobilières publiques,
agrégées par commune / département / région autour de la clé INSEE `code_commune`.

## Stack

- **API** : FastAPI (async, Pydantic v2) + SQLAlchemy / GeoAlchemy2
- **BDD** : PostgreSQL 16 + PostGIS 3.4
- **Big Data** : PySpark 3.5 (cluster Spark : 1 master + 2 workers)
- **Pipeline** : orchestrateur CLI unique [`src/pipeline.py`](src/pipeline.py)
- **Scraping** : Scrapy (avis ville-ideale.fr)
- **Outillage** : Poetry, Ruff, pytest, pre-commit, Docker Compose

## Prérequis

- Docker Desktop
- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)

## Démarrage rapide

```bash
git clone git@github.com:HomePedia-T-DAT-902/homepedia-api.git
cd homepedia-api

make setup   # copie .env, installe les deps Poetry, démarre PostgreSQL + Spark
```

> Le schéma SQL (tables + index + PostGIS) est créé **automatiquement** au premier
> démarrage de PostgreSQL via `docker-entrypoint-initdb.d`.

L'API est disponible sur `http://localhost:8000` — documentation Swagger : `http://localhost:8000/docs`.

### Tout lancer d'un coup

Une seule commande démarre les services, exécute le pipeline complet (les 9 sources) puis
lance l'API :

```bash
make all
```

> ⚠️ Le pipeline complet télécharge plusieurs Go (DVF surtout). Pour un premier essai,
> traiter d'abord les sources légères — voir ci-dessous.

## Commandes Make

```bash
make help        # liste toutes les cibles
make setup       # env + deps + services (db, spark)
make all         # services + pipeline complet + API  ← tout d'un coup
make pipeline    # pipeline complet (download → preprocess → process → load)
make api         # API en local avec hot reload (hors Docker)
make test        # pytest
make lint        # ruff check
make format      # ruff format
make ci          # lint + typecheck + test
make clean       # down des containers + purge data/raw et data/processed
```

## Pipeline de données

Le pipeline tourne dans le container `processing` et est piloté par une CLI unique.

```bash
# Pipeline complet (toutes les sources)
docker compose run --rm processing python -m src.pipeline run-all

# Sources spécifiques uniquement
docker compose run --rm processing python -m src.pipeline run --sources geo bpe

# Tout sauf les sources lourdes
docker compose run --rm processing python -m src.pipeline run-all --skip dvf

# Relancer sans re-télécharger (données brutes déjà présentes)
docker compose run --rm processing python -m src.pipeline run --sources bpe --skip-download

# Étapes individuelles
docker compose run --rm processing python -m src.pipeline download   --sources geo
docker compose run --rm processing python -m src.pipeline preprocess --sources bpe
docker compose run --rm processing python -m src.pipeline process    --sources geo bpe
docker compose run --rm processing python -m src.pipeline load        --sources geo bpe
```

### Sources disponibles

Les 9 sources branchées dans le pipeline (détails : [docs/sources.md](docs/sources.md)) :

| Source | Description | Fournisseur | Volume |
|--------|-------------|-------------|--------|
| `geo` | Communes, départements, régions (contours + population) | Etalab / INSEE | ~35 k communes |
| `bpe` | Équipements et services par commune | INSEE | ~1,8 M lignes |
| `dvf` | Transactions immobilières 2020-2025 | DGFiP / Etalab | ~10 M lignes |
| `iris` | Contours IRIS infra-communaux | IGN | ~49 k polygones |
| `ville_ideale` | Avis citoyens par commune (scraping) | ville-ideale.fr | à la demande |
| `crime` | Délinquance communale (5 catégories) | SSMSI | par commune/an |
| `education` | Résultats du bac (lycées GT) | MENJ (IVAL) | par commune/an |
| `risques` | Risques naturels et technologiques + géopoints | Géorisques (BRGM) | par commune |
| `qualite_air` | Indice ATMO annuel | ATMO France | par commune/an |

> **Note** : `dvf` représente plusieurs Go. Prévoir le téléchargement en conséquence.
> `geo` est la source socle (référentiel communes) : la charger en premier.

## Architecture

```
src/
  sources/           # Une source = un dossier autonome (config/download/preprocess/process/load/source)
    base.py          # Interface DataSource (ABC) : download → preprocess → process → load
    utils.py         # Utilitaires HTTP partagés
    geo/ bpe/ dvf/ iris/ ville_ideale/ crime/ education/ risques/ qualite_air/
  processing/
    spark_utils.py   # Helper SparkSession partagé
  database/
    postgres_schema.sql  # Schéma SQL (exécuté automatiquement au 1er démarrage de PostgreSQL)
  api/               # FastAPI : routers, services, repositories, schemas
  pipeline.py        # Orchestrateur CLI (registre des sources)

data/raw/            # Fichiers bruts téléchargés (non versionnés)
data/processed/      # Fichiers Parquet produits par Spark (non versionnés)
tests/               # Tests unitaires et d'intégration
```

### Interface DataSource

Chaque source implémente 4 étapes ([`src/sources/base.py`](src/sources/base.py)) :

```python
class MaSource(DataSource):
    def download(self)    -> None: ...  # Télécharge les fichiers bruts     → data/raw/
    def preprocess(self)  -> None: ...  # Valide / nettoie avant Spark      → data/raw/
    def process(self)     -> None: ...  # Job Spark → Parquet               → data/processed/
    def load(self)        -> None: ...  # Parquet → PostgreSQL
```

Ajouter une source = créer le dossier puis l'enregistrer dans le dictionnaire `SOURCES` de
[`src/pipeline.py`](src/pipeline.py).

## Tests

```bash
make test          # ou : poetry run pytest
```

## Documentation

- [Architecture](docs/architecture.md) — pipeline, API 3 couches, Docker
- [Sources de données](docs/sources.md) — les 9 sources intégrées
- [Schéma BDD](docs/database.md) — tables PostgreSQL / PostGIS
- [Contrat API](docs/api-contrat.md) — endpoints et schémas
- [Cahier des charges](docs/project.md)
