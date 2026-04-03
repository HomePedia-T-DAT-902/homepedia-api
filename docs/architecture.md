# Homepedia -- Architecture Technique

> **Version** : v2 — Mars 2026
> **Statut** : À valider par l'équipe

## Documents associés

| Doc | Audience | Contenu |
|-----|----------|---------|
| [api-contrat.md](api-contrat.md) | Backend + Frontend | Endpoints, schémas Pydantic, erreurs, mapping vues ↔ endpoints |
| [database.md](database.md) | Backend | Schéma SQL complet, PostGIS, indexation |
| [frontend.md](frontend.md) | Frontend | Navigation viewLevel, composants, hooks, config Vite |
| [datagouv-digest.md](datagouv-digest.md) | Tous | Sources de données (résumé) |
| [datagouv-sources.md](datagouv-sources.md) | Tous | Sources de données (détail, source de vérité) |

---

## 1. Vue d'ensemble

### Schéma global (flux de données)

```mermaid
graph TD
    subgraph Sources brutes
        SRC[DVF · DPE · BPE · INSEE<br/>Crime · Éducation · COG · GeoJSON<br/>ville-ideale · pap.fr]
    end

    subgraph Ingestion
        RAW[data/raw/]
    end

    subgraph Processing
        SPARK[PySpark<br/>Toutes sources]
        PARQUET[data/processed/<br/>Parquet]
    end

    subgraph Base de données
        PG[(PostgreSQL 16<br/>+ PostGIS 3.4)]
        DIM[Dimension<br/>communes, depts, regions]
        FAIT[Faits<br/>dvf_transactions, dpe_diag]
        ANAL[Analytique<br/>price_trends, stats]
        JSON[JSONB<br/>city_reviews, listings]
    end

    subgraph Backend
        API[FastAPI :8000<br/>Router - Service - Repository<br/>Cache fastapi-cache2]
    end

    subgraph Frontend
        REACT[React :5173<br/>react-map-gl · Recharts · Tailwind<br/>TanStack Query · viewLevel navigation]
    end

    SRC -->|scripts ingestion + scrapers| RAW
    RAW --> SPARK
    SPARK -->|colonnes = miroir schema SQL| PARQUET
    PARQUET -->|UPSERT loaders| PG
    PG --- DIM & FAIT & ANAL & JSON
    PG -->|SQLAlchemy + GeoAlchemy2 async| API
    API -->|JSON via fetch| REACT
```

### Communication frontend ↔ backend (microservices)

```mermaid
graph LR
    subgraph homepedia-front
        REACT[React SPA :5173/:80]
    end
    subgraph homepedia-api
        API[FastAPI :8000]
        PG[(PostgreSQL + PostGIS)]
    end
    REACT -->|HTTP REST via VITE_API_URL| API
    API -->|JSON| REACT
    API -->|SQLAlchemy async| PG
```

---

## 2. Structure du projet (2 repos)

### Repo `homepedia-api` (Backend)

```
src/
    ingestion/                       # 1 script par source (download_*.py)
    scraping/                        # Web scrapers (ville-ideale.fr, pap.fr)
    processing/                      # Jobs PySpark
    database/                        # Schema SQL, loaders PostgreSQL
    api/                             # FastAPI
        main.py                      # FastAPI app, CORS, /api/v1 prefix
        dependencies.py              # Depends: get_db
        exceptions.py                # HomepediaError + handlers
        schemas/                     # Pydantic v2 — contrat API
            commune.py               # RegionItem, DepartementItem, CommuneSearch, CommuneDetail
            price.py                 # PriceRecord, PriceTrend, PriceStats
            stats.py                 # CommuneStats, DpeDistribution, EquipmentCounts, ...
            geo.py                   # BBox, ChoroplethItem, ChoroplethData
            reviews.py               # ReviewRatings, ReviewSummary, WordCloudEntry
            pagination.py            # PaginatedResponse[T]
            errors.py                # ErrorDetail
        models/                      # SQLAlchemy ORM
            base.py                  # DeclarativeBase
            commune.py               # communes, departements, regions
            dvf.py                   # dvf_transactions
            dpe.py                   # dpe_diagnostics
            stats.py                 # commune_statistics, equipements, criminalite
            price_trend.py           # price_trends (pré-calculé)
            geo.py                   # colonnes PostGIS geometry
            review.py                # city_reviews
        repositories/                # Accès données (requêtes SQL)
            commune_repo.py
            price_repo.py
            stats_repo.py
            geo_repo.py              # Requêtes PostGIS (ST_Intersects, etc.)
            review_repo.py
        services/                    # Logique métier
            commune_service.py
            price_service.py
            stats_service.py
            geo_service.py
            review_service.py
        routers/                     # Routes HTTP
            communes.py
            prices.py
            stats.py
            geo.py
            reviews.py
data/raw/                            # Fichiers bruts (NON versionné)
data/processed/                      # Sorties Parquet (NON versionné)
tests/                               # pytest
Dockerfile                           # Python + uvicorn
docker-compose.yml                   # PostgreSQL + Spark + API
pyproject.toml                       # Poetry
Makefile
```

### Repo `homepedia-front` (Frontend)

```
src/
    main.tsx                         # Point d'entrée React
    App.tsx                          # Layout global (PAS de React Router)
    types/                           # Types TypeScript (miroir des schemas API)
        commune.ts, price.ts, stats.ts, geo.ts, reviews.ts
    api/                             # Client API centralisé (fetch)
        client.ts                    # fetchApi(), fetchGeoJson()
        communes.ts, prices.ts, stats.ts, geo.ts, reviews.ts
    hooks/                           # Custom React hooks
        useMapNavigation.ts          # viewLevel + selection
        useCommune.ts, usePrices.ts, useStats.ts, useGeo.ts, useReviews.ts
        useFilters.ts                # Context pour filtres globaux
    components/                      # Composants réutilisables
        Layout.tsx                   # Navbar, barre de recherche
        MapView.tsx                  # react-map-gl (choropleth, bubble, heatmap)
        SidePanel.tsx                # Panneau latéral contextuel
        Charts.tsx                   # Recharts (Line, Bar, Radar, Box)
        Filters.tsx                  # Filtres (date, type bien)
        KpiCards.tsx                 # Cartes KPI
        WordCloud.tsx                # Word cloud interactif
    views/                           # Vues contextuelles (dans SidePanel)
        NationalView.tsx             # viewLevel=national
        RegionView.tsx               # viewLevel=region
        DepartementView.tsx          # viewLevel=departement
        CommuneView.tsx              # viewLevel=commune
        TendancesView.tsx            # viewMode=tendances
        ComparaisonView.tsx          # viewMode=comparaison
        EnergieView.tsx              # viewMode=energie
        AvisView.tsx                 # viewMode=avis
tests/                               # vitest
Dockerfile                           # Multi-stage : Node build → Nginx
docker-compose.yml                   # Frontend (dev: Vite / prod: Nginx)
package.json
vite.config.ts
tailwind.config.ts
tsconfig.json
.env.example                         # VITE_API_URL=http://localhost:8000
```

---

## 3. Pipeline de données

### Flux par source

```
[Source brute] → [Ingestion] → [Processing] → [Table DB] → [API] → [Vue React]
```

| Source | Ingestion | Processing | Table(s) DB | Endpoint API | Vue(s) React |
|--------|-----------|------------|-------------|--------------|-------------|
| **DVF** | `download_dvf.py` | `spark_dvf.py` (PySpark) | `dvf_transactions`, `price_trends` | `/prices/{code}`, `/prices/trends/{dept}` | Accueil, Commune, Tendances |
| **DPE** | `download_dpe.py` | `spark_dpe.py` (PySpark) | `dpe_diagnostics` | `/stats/{code}` (DPE) | Commune, Énergie |
| **BPE** | `download_bpe.py` | `spark_aggregations.py` (PySpark) | `commune_equipements` | `/stats/{code}` (équipements) | Commune |
| **FiLoSoFi** | `download_insee.py` | `spark_aggregations.py` (PySpark) | `commune_statistics` | `/stats/{code}` (revenus) | Commune, Comparaison |
| **Populations** | `download_insee.py` | `spark_aggregations.py` (PySpark) | `commune_statistics` | `/stats/{code}` (démographie) | Commune, Comparaison |
| **France Travail** | `download_insee.py` | `spark_aggregations.py` (PySpark) | `commune_statistics` | `/stats/{code}` (emploi) | Commune, Comparaison |
| **Criminalité** | `download_crime.py` | `spark_aggregations.py` (PySpark) | `commune_criminalite` | `/stats/{code}` (criminalité) | Commune |
| **Éducation** | `download_education.py` | `spark_aggregations.py` (PySpark) | `commune_education` | `/stats/{code}` (éducation) | Commune |
| **Impôts** | `download_rei.py` | `spark_aggregations.py` (PySpark) | `commune_impots` | `/stats/{code}` (fiscalité) | Commune |
| **COG** | `download_geo.py` | chargement direct | `communes`, `departements`, `regions` | `/communes/*` | Toutes |
| **Contours GeoJSON** | `download_geo.py` | ST_GeomFromGeoJSON | `*.geom` (PostGIS) | `/geo/*` | Cartes |
| **Cadastre (parcelles)** | `download_cadastre.py` | `load_cadastre.py` (direct) | `parcelles_cadastrales` | `/geo/parcelles?bbox=` | Commune |
| **Carte des loyers** | `download_loyers.py` | `spark_aggregations.py` (PySpark) | `commune_loyers` | `/stats/{code}` (loyers) | Commune |
| **LOVAC** | `download_lovac.py` | `spark_aggregations.py` (PySpark) | `commune_logements_vacants` | `/stats/{code}` (vacance) | Commune |
| **Zonage ABC** | `download_zonage.py` | chargement direct | `commune_zonage_abc` | `/stats/{code}` (zonage) | Commune |
| **Ma Connexion Internet** | `download_internet.py` | `spark_aggregations.py` (PySpark) | `commune_internet` | `/stats/{code}` (internet) | Commune |
| **API Géorisques** | `download_georisques.py` | `spark_aggregations.py` (PySpark) | `commune_risques` | `/stats/{code}` (risques) | Commune |
| **Ensoleillement** | `download_ensoleillement.py` | chargement direct | `departement_ensoleillement` | `/stats/{code}` (climat) | Commune |
| **Prix de l'eau** | `download_eau.py` | `spark_aggregations.py` (PySpark) | `commune_eau` | `/stats/{code}` (eau) | Commune |
| **APL** | `download_apl.py` | `spark_aggregations.py` (PySpark) | `commune_apl` | `/stats/{code}` (santé) | Commune |
| **RPLS** | `download_rpls.py` | `spark_aggregations.py` (PySpark) | `rpls_logements` | `/geo/rpls?bbox=` | Commune |
| **Comptes communes** | `download_comptes.py` | `spark_aggregations.py` (PySpark) | `commune_comptes` | `/stats/{code}` (finances) | Commune |
| **Nuance politique** | `download_politique.py` | chargement direct | `commune_politique` | `/stats/{code}` (politique) | Commune |
| **Déplacements** | `download_navettes.py` | `spark_aggregations.py` (PySpark) | `commune_navettes` | `/stats/{code}` (transport) | Commune |
| **ville-ideale** | `ville_ideale_scraper.py` | `spark_reviews.py` | `city_reviews` (JSONB) | `/reviews/{code}` | Commune, Avis |
| **pap.fr** | `pap_scraper.py` | chargement JSON | `listings` (JSONB) | `/stats/{code}` (annonces) | Commune |

> Détail des schémas SQL : voir [database.md](database.md)
> Détail des endpoints et schémas Pydantic : voir [api-contrat.md](api-contrat.md)

---

## 4. Architecture backend (3 couches)

```mermaid
graph LR
    CLIENT[Client HTTP] --> ROUTER[Router<br/>Valide la requête<br/>Retourne le schema<br/>Gère erreurs HTTP]
    ROUTER --> SERVICE[Service<br/>Orchestre les repos<br/>Combine les sources<br/>Applique règles métier]
    SERVICE --> REPO[Repository<br/>Requêtes SQL/PostGIS<br/>Responsabilité unique<br/>Retourne des models]
    REPO --> DB[(PostgreSQL<br/>+ PostGIS)]
```

### Exemple de flux : `GET /api/v1/communes/{code}`

```python
# 1. Router — src/api/routers/communes.py
@router.get("/communes/{code}", response_model=CommuneDetail)
async def get_commune(code: str, db: AsyncSession = Depends(get_db)):
    service = CommuneService(db)
    return await service.get_detail(code)

# 2. Service — src/api/services/commune_service.py
class CommuneService:
    def __init__(self, db: AsyncSession):
        self.commune_repo = CommuneRepository(db)
        self.review_repo = ReviewRepository(db)

    async def get_detail(self, code: str) -> CommuneDetail:
        commune = await self.commune_repo.get_by_code(code)
        if not commune:
            raise HomepediaError("COMMUNE_NOT_FOUND", f"Commune {code} introuvable", 404)
        review = await self.review_repo.get_summary(code)
        return CommuneDetail(
            code_commune=commune.code_commune,
            nom=commune.nom,
            # ... mapper tous les champs ...
            note_globale=review.note_globale if review else None,
        )

# 3. Repository — src/api/repositories/commune_repo.py
class CommuneRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_code(self, code: str) -> CommuneModel | None:
        stmt = select(CommuneModel).where(CommuneModel.code_commune == code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
```

---

## 5. Cache

```mermaid
graph LR
    REACT[React] -->|fetch| CACHE_F[TanStack Query<br/>staleTime 5min-1h]
    CACHE_F -->|miss| API[FastAPI]
    API -->|check| CACHE_B[fastapi-cache2<br/>TTL 1h-24h]
    CACHE_B -->|miss| PG[(PostgreSQL)]
```

| Niveau | Outil | Quoi cacher | TTL |
|--------|-------|-------------|-----|
| **API** | `fastapi-cache2` (in-memory) | Réponses API | 1h-24h selon endpoint |
| **Frontend** | TanStack Query (staleTime) | Données API en mémoire | 5min-1h selon donnée |

**Règles** :
- TanStack Query gère automatiquement le cache, la déduplication et le refetch
- GeoJSON : TTL 24h (changent rarement)
- Prix/stats : TTL 6h (changent après un run du pipeline)
- Recherche : staleTime 5min

---

## 6. CI/CD (GitHub Actions)

Chaque repo a sa propre pipeline CI/CD.

### Pipeline `homepedia-api`

```mermaid
graph TD
    PUSH[Push / PR] --> LINT[lint<br/>ruff + mypy]
    LINT --> TEST[test<br/>pytest + PostGIS réel]
    TEST --> BUILD[docker build<br/>+ push image]
```

### Pipeline `homepedia-front`

```mermaid
graph TD
    PUSH[Push / PR] --> LINT[lint<br/>eslint + tsc --noEmit]
    LINT --> TEST[test<br/>vitest + npm run build]
    TEST --> BUILD[docker build<br/>target prod + push image]
```

### Outils de qualité

| Outil | Scope | Rôle |
|-------|-------|------|
| **ruff** | Python | Linter + formatter |
| **mypy** | Python (`src/api/`) | Vérification de types |
| **ESLint** | TypeScript | Linter frontend |
| **tsc --noEmit** | TypeScript | Vérification de types |
| **pytest** | Python | Tests unitaires + intégration |
| **vitest** | TypeScript | Tests unitaires frontend |

### Dépendances dev

**`pyproject.toml`** :
```toml
[tool.poetry.group.dev.dependencies]
ruff = "^0.8"
mypy = "^1.13"
pytest = "^8.0"
pytest-asyncio = "^0.24"
httpx = "^0.28"
```

**`package.json`** :
```json
{
  "devDependencies": {
    "vitest": "^2.0",
    "eslint": "^9.0",
    "@typescript-eslint/eslint-plugin": "^8.0",
    "@typescript-eslint/parser": "^8.0"
  },
  "scripts": {
    "lint": "eslint src/",
    "test": "vitest"
  }
}
```

---

## 7. Infrastructure Docker

### Architecture microservices

Chaque repo a son propre `Dockerfile` et `docker-compose.yml`. Tous les services tournent en conteneurs, en dev comme en prod.

### `homepedia-api/docker-compose.yml`

```yaml
services:
  postgres:
    image: postgis/postgis:16-3.4
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: homepedia
      POSTGRES_USER: homepedia
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U homepedia"]
      interval: 5s
      retries: 5

  spark-master:
    image: bitnami/spark:3.5
    ports: ["8080:8080", "7077:7077"]

  spark-worker-1:
    image: bitnami/spark:3.5
    depends_on: [spark-master]

  spark-worker-2:
    image: bitnami/spark:3.5
    depends_on: [spark-master]

  api:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://homepedia:${POSTGRES_PASSWORD}@postgres:5432/homepedia
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./src:/app/src    # Hot reload en dev
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  pgdata:

networks:
  default:
    name: homepedia-network
```

### `homepedia-api/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Dépendances système pour psycopg2 et PostGIS
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Installation des dépendances Python
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-root

COPY . .

EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `homepedia-front/docker-compose.yml`

```yaml
services:
  frontend:
    build:
      context: .
      target: dev          # Changer en "prod" pour la production
    ports:
      - "5173:5173"        # Dev (Vite)
      # - "80:80"          # Prod (Nginx)
    environment:
      VITE_API_URL: http://localhost:8000
    volumes:
      - ./src:/app/src     # Hot reload en dev
      - /app/node_modules  # Éviter d'écraser node_modules

networks:
  default:
    name: homepedia-network
```

### `homepedia-front/Dockerfile`

```dockerfile
# ---- Stage dev : Vite dev server (hot reload) ----
FROM node:20-alpine AS dev
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

# ---- Stage prod : build static + Nginx ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### `homepedia-front/nginx.conf`

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # SPA : toutes les routes renvoient index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API (optionnel, si front et back sur le même domaine)
    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Cache assets statiques
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Lancement

```bash
# Dev — dans chaque repo séparément :
cd homepedia-api && docker-compose up -d
cd homepedia-front && docker-compose up -d

# Prod — build avec le target prod :
cd homepedia-front && docker-compose build --build-arg VITE_API_URL=https://api.homepedia.fr
```

---

## 8. Vérification de l'architecture

Pour valider que tout fonctionne avant de développer les features :

1. **Repo `homepedia-api`** : créer `src/api/main.py` avec un endpoint stub `GET /api/v1/communes/search?q=lyon` → JSON hardcodé
2. **Repo `homepedia-front`** : créer le projet Vite + `App.tsx` (Layout + MapView + SidePanel)
3. `docker-compose up -d` dans chaque repo
4. Vérifier le round-trip : React → fetch (`VITE_API_URL`) → FastAPI → JSON → React → affichage SidePanel
5. Vérifier que le clic carte déclenche `navigateTo()` et que le SidePanel change de vue
6. Tester sur `http://localhost:5173` (front) et `http://localhost:8000/docs` (API Swagger)

Si ce round-trip fonctionne entre les deux conteneurs et que la navigation viewLevel marche, l'architecture est validée.
