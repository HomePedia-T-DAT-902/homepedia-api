# Pipeline Cadastre — HomePedia

## Vue d'ensemble

Le pipeline cadastre permet d'intégrer les **~70 millions de parcelles cadastrales françaises** (source Etalab) dans la base PostgreSQL/PostGIS de HomePedia, et de les exposer via l'API.

```
Etalab (data.gouv.fr)
        │
        ▼
[1. Téléchargement]  download_cadastre.py
        │  GeoJSON.gz (1 fichier / département)
        ▼
[2. Chargement BDD]  load_cadastre.py
        │  Streaming + COPY batch → PostgreSQL/PostGIS
        ▼
[3. API REST]        /api/v1/geo/parcelles
```

---

## 1. Source de données

- **Fournisseur** : Etalab — Plan Cadastral Informatisé
- **Format** : GeoJSON compressé (`.geojson.gz`), un fichier par département
- **Volume** : ~70 M parcelles, 40–60 GB décompressé
- **Couverture** : France métropolitaine (01–95, 2A, 2B) + DOM (971–976)

---

## 2. Ingestion — `download_cadastre.py`

Télécharge les fichiers GeoJSON depuis Etalab et les stocke compressés dans `data/raw/cadastre/`.

**Comportement :**
- Téléchargement en streaming (chunks de 1 MB) → pas de pic mémoire
- Les bytes gzip sont conservés bruts (le loader décompresse à la volée)
- Idempotent : saute les fichiers déjà présents (`--force` pour écraser)

**Commandes :**
```bash
python -m src.ingestion.download_cadastre              # tous les depts
python -m src.ingestion.download_cadastre --dept 75    # Paris uniquement
python -m src.ingestion.download_cadastre --force      # re-télécharge tout
```

---

## 3. Chargement BDD — `load_cadastre.py`

Charge les fichiers `.geojson.gz` dans la table `parcelles_cadastrales` via PostgreSQL.

### Stratégie technique

**Parsing streaming (O(1) mémoire)**
- Utilise `ijson` pour lire les features une par une sans charger le GeoJSON complet en mémoire
- Fallback sur `json.load` si `ijson` n'est pas installé (risque OOM sur gros départements)

**Insertion par batch via table temporaire**
```
GeoJSON features
      ↓ (batch 50 000)
  tmp_cadastre (table temp CSV)
      ↓ COPY FROM STDIN
  parcelles_cadastrales
      ↓ ST_GeomFromGeoJSON() + ST_SetSRID()
  geom GEOMETRY(Polygon, 4326)
```

- Chaque batch est copié en CSV dans `tmp_cadastre` via `COPY FROM STDIN` (très rapide)
- Puis converti et inséré dans la table finale avec `ST_GeomFromGeoJSON`
- **UPSERT** (`ON CONFLICT DO UPDATE`) : chargement incrémental possible

**Commandes :**
```bash
python -m src.database.load_cadastre                   # tous les fichiers présents
python -m src.database.load_cadastre --dept 75 13 69   # Paris, BdR, Rhône
python -m src.database.load_cadastre --truncate        # vide la table avant chargement
```

---

## 4. Schéma de la table

```sql
CREATE TABLE parcelles_cadastrales (
    id           VARCHAR(20) PRIMARY KEY,   -- identifiant Etalab
    code_commune VARCHAR(5),               -- FK → communes
    prefixe      VARCHAR(3),
    section      VARCHAR(2),
    numero       VARCHAR(4),
    contenance   INTEGER,                   -- surface en m²
    created      DATE,
    updated      DATE,
    geom         GEOMETRY(Polygon, 4326)   -- contour géographique WGS84
);
```

**Index :**
- `idx_parcelles_geom` — GiST (requêtes spatiales, bbox)
- `idx_parcelles_code_commune` — B-tree (filtres par commune)
- `idx_parcelles_section` — B-tree

---

## 5. API REST — Endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/v1/geo/parcelles?bbox=...` | Parcelles dans une bounding box |
| `GET` | `/api/v1/geo/parcelles/{id}` | Détail d'une parcelle |
| `GET` | `/api/v1/geo/communes/{code}/parcelles` | Toutes les parcelles d'une commune |

**Requête spatiale (bbox) :**
```sql
WHERE geom && ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
LIMIT 5000  -- max 10 000
```

**Réponse :** GeoJSON `FeatureCollection` standard, avec flag `truncated` si la limite est atteinte.

---

## 6. Choix techniques clés

| Contrainte | Solution retenue |
|------------|-----------------|
| ~70 M features, fichiers > 1 GB | Parsing streaming `ijson` + batch 50 000 |
| Insertion rapide | `COPY FROM STDIN` CSV (x5–10 vs INSERT) |
| Mises à jour sans doublon | UPSERT `ON CONFLICT (id) DO UPDATE` |
| Requêtes spatiales performantes | Index GiST PostGIS sur `geom` |
| Stockage disque | Fichiers `.geojson.gz` conservés compressés |
