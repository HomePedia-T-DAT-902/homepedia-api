# Contrat API

> **Source de vérité pour l'interface backend ↔ frontend.**
> Pour le contexte global de l'architecture, voir [architecture.md](architecture.md).

---

## Règles générales

- **Base URL** : `/api/v1` — tous les endpoints sont préfixés par ce chemin.
- **Format** : toutes les réponses sont en **JSON** (`Content-Type: application/json`).
- **Règle stricte** : le frontend ne doit **JAMAIS** utiliser un champ non défini dans ce contrat. Si un champ manque, l'ajouter au schéma Pydantic d'abord.
- **Communication microservices** : le frontend (`homepedia-front`) appelle l'API via la variable d'env `VITE_API_URL`. En production, le reverse proxy Nginx route `/api/` vers le backend.

```typescript
// src/api/client.ts (repo homepedia-front)
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
// Dev : VITE_API_URL=http://localhost:8000
// Prod : VITE_API_URL=https://api.homepedia.fr (ou routé via Nginx)
```

---

## Tableau des endpoints

| Endpoint | Méthode | Response | Cache | Params |
|----------|---------|----------|-------|--------|
| `/api/v1/communes/search` | GET | `list[CommuneSearch]` | 1h | `q` (string, min 2 chars) |
| `/api/v1/communes/{code}` | GET | `CommuneDetail` | 1h | — |
| `/api/v1/communes/regions` | GET | `list[RegionItem]` | 24h | — |
| `/api/v1/communes/departments` | GET | `list[DepartementItem]` | 24h | `region` (code_region) |
| `/api/v1/prices/{code_commune}` | GET | `PriceStats` | 6h | `period`, `type` |
| `/api/v1/prices/trends/{code_dept}` | GET | `list[PriceTrend]` | 6h | — |
| `/api/v1/stats/{code_commune}` | GET | `CommuneStats` | 6h | — |
| `/api/v1/geo/communes` | GET | `GeoJSON FeatureCollection` | 24h | `bbox` |
| `/api/v1/geo/departments` | GET | `GeoJSON FeatureCollection` | 24h | — |
| `/api/v1/geo/choropleth` | GET | `ChoroplethData` | 6h | `indicator`, `level` |
| `/api/v1/reviews/{code_commune}` | GET | `ReviewSummary` | 6h | — |
| `/api/v1/geo/transactions` | GET | `GeoJSON FeatureCollection` | 6h | `bbox`, `type`, `annee` |
| `/api/v1/geo/rpls` | GET | `GeoJSON FeatureCollection` | 24h | `bbox` |

---

## Schémas Pydantic

### Communes

**`schemas/commune.py`**

```python
class RegionItem(BaseModel):
    code_region: str           # "84"
    nom: str                   # "Auvergne-Rhône-Alpes"

class DepartementItem(BaseModel):
    code_departement: str      # "69"
    nom: str                   # "Rhône"
    code_region: str

class CommuneSearch(BaseModel):
    code_commune: str          # "69123"
    nom: str                   # "Lyon"
    code_postal: str | None
    nom_departement: str
    nom_region: str

class CommuneDetail(CommuneSearch):
    code_departement: str
    code_region: str
    population: int | None
    superficie: float | None
    densite: float | None
    latitude: float | None
    longitude: float | None
    prix_median_m2: float | None
    nb_transactions_annee: int | None
    revenu_median: float | None
    taux_pauvrete: float | None
    taux_chomage: float | None
    classe_dpe_dominante: str | None
    note_globale: float | None
    nb_avis: int | None
    zone_abc: str | None
    loyer_median_m2: float | None
    taux_vacance: float | None
    nb_logements_sociaux: int | None
```

### Prix

**`schemas/price.py`**

```python
class PriceRecord(BaseModel):
    date_mutation: date
    valeur_fonciere: float
    type_local: str
    surface_bati: float
    nb_pieces: int | None
    surface_terrain: float | None
    prix_m2: float

class PriceTrend(BaseModel):
    annee: int
    trimestre: int
    type_local: str
    prix_median_m2: float
    nb_transactions: int
    variation_annuelle_pct: float | None

class PriceStats(BaseModel):
    code_commune: str
    prix_median_m2: float | None
    prix_moyen_m2: float | None
    nb_transactions_total: int
    trends: list[PriceTrend]
    distribution_type_local: dict[str, int]
    prix_min_m2: float | None
    prix_max_m2: float | None
```

### Statistiques

**`schemas/stats.py`**

```python
class DpeDistribution(BaseModel):
    classe_a: int
    classe_b: int
    classe_c: int
    classe_d: int
    classe_e: int
    classe_f: int
    classe_g: int
    consommation_moyenne: float | None

class EquipmentCounts(BaseModel):
    nb_ecoles: int
    nb_colleges: int
    nb_lycees: int
    nb_medecins: int
    nb_dentistes: int
    nb_pharmacies: int
    nb_hopitaux: int
    nb_gares: int
    nb_supermarches: int
    nb_total: int

class CriminalityStats(BaseModel):
    annee: int
    # ... 15 indicateurs ...
    total_faits: int
    population: int | None
    taux_pour_mille: float | None

class LoyerStats(BaseModel):
    loyer_m2_appartement: float | None
    loyer_m2_maison: float | None
    loyer_m2_app_3p: float | None
    loyer_m2_app_12p: float | None

class VacanceStats(BaseModel):
    annee: int
    nb_logements_total: int
    nb_vacants: int
    nb_vacants_longue_duree: int
    taux_vacance: float

class ZonageABC(BaseModel):
    zone: str
    reclassement: bool

class RplsStats(BaseModel):
    nb_logements_sociaux: int
    surface_moyenne: float | None
    repartition_financement: dict[str, int]
    repartition_dpe: dict[str, int] | None

class CommuneStats(BaseModel):
    code_commune: str
    revenu_median: float | None
    taux_pauvrete: float | None
    taux_chomage: float | None
    population: int | None
    dpe: DpeDistribution | None
    equipements: EquipmentCounts | None
    criminalite: list[CriminalityStats]
    loyers: LoyerStats | None
    rpls: RplsStats | None
    vacance: list[VacanceStats]
    zonage_abc: ZonageABC | None
```

### Géo

**`schemas/geo.py`**

```python
class BBox(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

class ChoroplethItem(BaseModel):
    code: str
    nom: str
    valeur: float

class ChoroplethData(BaseModel):
    indicator: str
    level: str
    items: list[ChoroplethItem]
    geojson: dict[str, Any]
```

### Avis

**`schemas/reviews.py`**

```python
class ReviewRatings(BaseModel):
    environnement: float | None
    transports: float | None
    securite: float | None
    sante: float | None
    sports_loisirs: float | None
    culture: float | None
    education: float | None
    commerces: float | None

class WordCloudEntry(BaseModel):
    mot: str
    frequence: int

class ReviewSummary(BaseModel):
    code_commune: str
    note_globale: float | None
    nb_avis: int
    ratings: ReviewRatings | None
    word_cloud: list[WordCloudEntry]
```

### Commun

**`schemas/pagination.py`**

```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool
```

**`schemas/errors.py`**

```python
class ErrorDetail(BaseModel):
    code: str        # "COMMUNE_NOT_FOUND"
    message: str
```

---

## Gestion d'erreurs

Format de réponse d'erreur :

```json
{ "code": "COMMUNE_NOT_FOUND", "message": "Commune 99999 introuvable" }
```

| Code HTTP | Code erreur | Quand |
|-----------|-------------|-------|
| 400 | `INVALID_BBOX` | bbox mal formée |
| 400 | `INVALID_INDICATOR` | indicateur choropleth inconnu |
| 404 | `COMMUNE_NOT_FOUND` | code_commune inexistant |
| 404 | `DEPARTMENT_NOT_FOUND` | code_departement inexistant |
| 422 | (FastAPI auto) | Validation Pydantic échouée |

---

## Correspondance vues ↔ endpoints

| Vue | Déclencheur | Endpoints API | Carte |
|-----|-------------|---------------|-------|
| **NationalView** | `viewLevel=national` | `/geo/departments`, `/geo/choropleth` | Choropleth départements |
| **RegionView** | `viewLevel=region` | `/geo/choropleth`, `/prices/trends/{dept}` | Zoom région, depts colorés |
| **DepartementView** | `viewLevel=departement` | `/geo/communes?bbox=`, `/prices/trends/{dept}` | Zoom dept, bubble map communes |
| **CommuneView** | `viewLevel=commune` | `/communes/{code}`, `/prices/{code}`, `/stats/{code}`, `/reviews/{code}`, `/geo/transactions?bbox=`, `/geo/rpls?bbox=` | Zoom commune, points cliquables |
| **TendancesView** | `viewMode=tendances` | `/prices/{code}` (x N communes) | — |
| **ComparaisonView** | `viewMode=comparaison` | `/communes/{code}` + `/stats/{code}` (x 2-4) | — |
| **EnergieView** | `viewMode=energie` | `/geo/choropleth?indicator=classe_dpe` | Heatmap DPE |
| **AvisView** | `viewMode=avis` | `/reviews/{code}`, `/geo/choropleth?indicator=note_globale` | Choropleth notes |
