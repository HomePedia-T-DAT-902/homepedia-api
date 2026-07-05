# Homepedia API — Suivi des tâches

> Projet T-DAT-902 — plateforme d'analyse du marché immobilier français.
> Ce fichier reflète l'état **réel** du repo `homepedia-api`. Détail des sources : [docs/sources.md](docs/sources.md).

Légende : `[x]` fait · `[ ]` à faire.

---

## Infrastructure & outillage

- [x] Repo Git + `.gitignore` (data/, .env, caches)
- [x] `pyproject.toml` (Poetry) — groupes `main`, `bigdata`, `scraping`, `utils`, `dev`
- [x] `docker-compose.yml` — `db` (PostgreSQL 16 + PostGIS 3.4), `spark-master` + 2 workers, `processing`, `api`
- [x] `Dockerfile` (API) et `Dockerfile.processing` (pipeline PySpark + Java)
- [x] `.env.example` (connexion DB, Spark, API)
- [x] `src/database/postgres_schema.sql` — tables + index (B-tree, GiST, GIN trigram), monté en init PostgreSQL
- [x] `Makefile` — `setup`, `all`, `pipeline`, `api`, `lint`, `format`, `test`, `ci`, `clean`
- [x] `README.md`
- [x] Pre-commit (ruff + hygiène + pytest au push)
- [x] CI GitHub Actions — lint (ruff) + tests (pytest) + docker build

---

## Pipeline & sources

- [x] Interface `DataSource` (`src/sources/base.py`) — download → preprocess → process → load
- [x] Orchestrateur CLI `src/pipeline.py` — registre `SOURCES`, commandes `run` / `run-all` / étapes
- [x] Helper Spark partagé `src/processing/spark_utils.py`

Sources intégrées (9) — chacune : `config / download / preprocess / process / load / source` :

- [x] `geo` — communes, départements, régions (contours + population)
- [x] `bpe` — équipements par commune
- [x] `dvf` — transactions immobilières 2020-2025 (+ `price_trends`)
- [x] `iris` — contours IRIS
- [x] `ville_ideale` — avis (Scrapy + récupération à la demande)
- [x] `crime` — délinquance communale (SSMSI)
- [x] `education` — résultats du bac (IVAL)
- [x] `risques` — risques naturels/technologiques + géopoints (Géorisques)
- [x] `qualite_air` — indice ATMO

---

## API (FastAPI)

- [x] Config async (`src/api/config.py`) — engine SQLAlchemy asyncpg + `get_db`
- [x] App + CORS + `/health` (`src/api/main.py`)
- [x] `communes` — recherche, régions, départements, fiche commune (pattern service/repository)
- [x] `geo` — IRIS par bbox / par commune (GeoJSON)
- [x] `prix` — points DVF agrégés par coordonnées
- [x] `reviews` — avis (cache-first + scrape à la demande)
- [x] `risques` — par commune, liste filtrée, géopoints
- [x] `qualite-air` — indice ATMO par commune
- [x] `securite` — délinquance par commune (historique)
- [x] `education` — résultats bac par commune (historique)
- [x] `equipements` — BPE par commune

---

## Tests

- [x] `tests/sources/` — download BPE, download DVF, ville_ideale (scraper, throttle, on-demand, pipeline)
- [x] `tests/api/` — communes
- [ ] Étendre la couverture API (geo, prix, risques, qualite-air, securite, education, equipements)
- [ ] Test d'intégration pipeline complet (raw → process → load → API)

---

## Documentation

- [x] [README.md](README.md), [architecture](docs/architecture.md), [sources](docs/sources.md),
  [database](docs/database.md), [contrat API](docs/api-contrat.md)
- [x] [Source ville-ideale.fr](docs/data-source-ville-ideale.md)
