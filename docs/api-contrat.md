# Contrat API

> **Source de vérité pour l'interface backend ↔ frontend.**
> Reflète les routers réellement montés dans [`src/api/main.py`](../src/api/main.py).
> Le schéma complet et interactif est toujours disponible sur `http://localhost:8000/docs`.

---

## Règles générales

- **Préfixe** : tous les endpoints métier sont sous `/api/v1`. `GET /health` est le seul hors préfixe.
- **Format** : réponses **JSON** (`Content-Type: application/json`).
- **CORS** : ouvert (`allow_origins=["*"]`) — le frontend appelle l'API via `VITE_API_URL`.
- Le frontend ne doit **jamais** consommer un champ non listé ici : l'ajouter d'abord au schéma Pydantic.

---

## Tableau des endpoints

| Endpoint | Méthode | Response | Params |
|----------|---------|----------|--------|
| `/health` | GET | `{ "status": "ok" }` | — |
| `/api/v1/communes/search` | GET | `list[CommuneSearch]` | `q` (requis, ≥ 2 car.), `limit` (1-100, défaut 20) |
| `/api/v1/communes/regions` | GET | `list[RegionItem]` | — |
| `/api/v1/communes/departments` | GET | `list[DepartementItem]` | `region` (code_region, optionnel) |
| `/api/v1/communes/{code_commune}` | GET | `CommuneDetail` | — |
| `/api/v1/geo/iris` | GET | `GeoJSONFeatureCollection` | `bbox`, `code_commune`, `limit` (1-50000, défaut 5000) |
| `/api/v1/geo/communes/{code_commune}/iris` | GET | `GeoJSONFeatureCollection` | — |
| `/api/v1/prix/points` | GET | `list[TransactionPoint]` | `bbox` (requis), `annee`, `type_local`, `limit` |
| `/api/v1/reviews/{code_commune}` | GET | `ReviewSummary` | — (cache-first, scrape à la demande) |
| `/api/v1/risques/geopoints` | GET | `list[RisqueGeopoint]` | `bbox`, `type_risque`, `code_commune`, `limit` (1-5000, défaut 100) |
| `/api/v1/risques/{code_commune}` | GET | `CommuneRisques` | — |
| `/api/v1/risques` | GET | `list[CommuneRisques]` | `inondation`, `seisme`, `feu_foret`, `radon`, `limit` (1-1000, défaut 100) |
| `/api/v1/qualite-air/{code_commune}` | GET | `CommuneQualiteAir` | — |
| `/api/v1/securite/{code_commune}` | GET | `CommuneSecurite` | — |
| `/api/v1/education/{code_commune}` | GET | `CommuneEducation` | — |
| `/api/v1/equipements/{code_commune}` | GET | `CommuneEquipements` | — |

> Le paramètre `bbox` a toujours le format `min_lon,min_lat,max_lon,max_lat`.

---

## Schémas Pydantic

### Communes — `schemas/commune.py`

```python
class CommuneSearch(BaseModel):
    code_commune: str
    nom: str
    code_postal: str | None = None
    nom_departement: str | None = None
    nom_region: str | None = None

class CommuneDetail(CommuneSearch):
    code_departement: str | None = None
    code_region: str | None = None
    population: int | None = None
    superficie: float | None = None
    densite: float | None = None
    latitude: float | None = None
    longitude: float | None = None

class RegionItem(BaseModel):
    code_region: str
    nom: str

class DepartementItem(BaseModel):
    code_departement: str
    nom: str
    code_region: str | None = None
```

### Géo (IRIS) — `schemas/geo.py`

```python
class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    properties: dict[str, Any]
    geometry: dict[str, Any]

class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    code_commune: str | None = None
    truncated: bool | None = None
    count: int
    features: list[GeoJSONFeature]
```

### Prix (DVF) — `routers/prix.py`

```python
class TransactionPoint(BaseModel):
    latitude: float
    longitude: float
    prix_m2_moyen: float
    nb_transactions: int
```

Les points DVF sont agrégés par coordonnées (`GROUP BY latitude, longitude`) : `prix_m2_moyen`
est la moyenne du prix/m² et `nb_transactions` le nombre de ventes au même point.

### Avis — `routers/reviews.py`

```python
class ReviewRatings(BaseModel):   # notes 0-10, 9 critères ville-ideale.fr
    environnement: float | None
    transports: float | None
    securite: float | None
    sante: float | None
    sports_loisirs: float | None
    culture: float | None
    enseignement: float | None
    commerces: float | None
    qualite_vie: float | None

class WordCloudEntry(BaseModel):
    mot: str
    frequence: int

class ReviewSummary(BaseModel):
    code_commune: str
    note_globale: float | None = None
    nb_avis: int
    ratings: ReviewRatings | None = None
    word_cloud: list[WordCloudEntry] = []
```

### Risques — `routers/risques.py`

```python
class CommuneRisques(BaseModel):
    code_commune: str
    inondation: bool | None
    seisme: bool | None
    mouvement_terrain: bool | None
    retrait_gonflement_argile: bool | None
    radon: bool | None
    feu_foret: bool | None
    icpe: bool | None
    source_annee: int | None

class RisqueGeopoint(BaseModel):
    id: int
    type_risque: str
    longitude: float
    latitude: float
    code_commune: str | None = None
```

### Qualité de l'air — `routers/qualite_air.py`

```python
class CommuneQualiteAir(BaseModel):
    code_commune: str
    annee: int | None
    indice_atmo: float | None
    nb_jours_bon: int | None
    nb_jours_moyen: int | None
    nb_jours_degrade: int | None
    nb_jours_mauvais: int | None
    nb_jours_tres_mauvais: int | None
    nb_jours_extremement_mauvais: int | None
```

### Sécurité — `routers/securite.py`

```python
class SecuriteAnnee(BaseModel):
    annee: int
    cambriolages_nombre: int | None
    cambriolages_pour_mille: float | None
    violences_nombre: int | None
    violences_pour_mille: float | None
    vols_nombre: int | None
    vols_pour_mille: float | None
    stups_nombre: int | None
    stups_pour_mille: float | None
    destructions_nombre: int | None
    destructions_pour_mille: float | None

class CommuneSecurite(BaseModel):
    code_commune: str
    historique: list[SecuriteAnnee]   # une entrée par année disponible
```

### Éducation — `routers/education.py`

```python
class EducationAnnee(BaseModel):
    annee: int
    bac_presents: int | None
    bac_taux_reussite: float | None

class CommuneEducation(BaseModel):
    code_commune: str
    historique: list[EducationAnnee]
```

### Équipements (BPE) — `routers/bpe.py`

```python
class CommuneEquipements(BaseModel):
    code_commune: str
    nb_equipements_total: int | None
    nb_maternelles: int | None
    nb_primaires: int | None
    nb_creches: int | None
    nb_colleges: int | None
    nb_lycees: int | None
    nb_medecins: int | None
    nb_pharmacies: int | None
    nb_urgences: int | None
    nb_supermarches: int | None
    nb_hypermarches: int | None
    nb_gares: int | None
```

---

## Gestion d'erreurs

FastAPI renvoie les erreurs au format `{ "detail": "..." }`.

| Code HTTP | Quand |
|-----------|-------|
| 400 | `bbox` mal formée (`/prix/points`, `/risques/geopoints`) |
| 404 | Ressource introuvable (commune sans donnée pour la thématique demandée) |
| 422 | Validation Pydantic échouée (paramètre manquant / hors bornes) |
| 503 | `/reviews/{code}` — ville-ideale.fr momentanément rate-limité et aucune copie en cache |
