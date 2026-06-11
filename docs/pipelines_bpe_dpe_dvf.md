# Pipelines BPE, DPE, DVF — HomePedia

---

## Vue d'ensemble

```
                     TÉLÉCHARGEMENT                    TRAITEMENT SPARK
                     ─────────────                    ────────────────
BPE  data.gouv.fr → Parquet → CSV ──────────────────► spark_bpe.py → Parquet (commune_stats)
DPE  API ADEME    → CSV paginé    ──────────────────► spark_dpe.py → Parquet (diagnostics + commune_stats)
DVF  Etalab/DGFiP → CSV/zip      ──────────────────► spark_dvf.py → Parquet partitionné par annee
```

---

## 1. BPE — Base Permanente des Équipements

### Source
- **Fournisseur** : INSEE via data.gouv.fr
- **Format** : Parquet (`BPE24.parquet`, ~200 MB), converti en CSV
- **Volume** : ~1,8 M équipements, ~35 000 communes
- **Colonne clé** : `DEPCOM` (code commune), `TYPEQU` (229 types : A101=maternelle, D201=médecin…)

### Téléchargement — `download_bpe.py`

1. Interroge l'API data.gouv.fr pour obtenir l'URL du fichier (Parquet en priorité, fallback CSV)
2. Télécharge en streaming (`requests`, chunks 1 MB)
3. **Conversion Parquet → CSV** via `pandas` (séparateur `;`)
4. Idempotent — saute si déjà présent (`--force` pour écraser)

```bash
python -m src.ingestion.download_bpe
python -m src.ingestion.download_bpe --force
```

### Traitement Spark — `spark_bpe.py`

1. Lecture du CSV (séparateur `;`, UTF-8)
2. Normalisation : `DEPCOM` → `code_commune` 5 chars (lpad)
3. Filtre TYPEQU invalides (`^[A-F][0-9]{2,3}$`)
4. **Agrégation par commune** :
   - Total équipements
   - Par grande catégorie (A=Enseignement, B=Sport, C=Commerce, D=Santé, E=Transport, F=Tourisme)
   - Types clés immobilier : maternelles, primaires, crèches, collèges, lycées, médecins, pharmacies, urgences, supermarchés, gares
5. Export Parquet → `data/processed/bpe/commune_stats/`

```bash
docker-compose run --rm processing python -m src.processing.spark_bpe
```

---

## 2. DPE — Diagnostics de Performance Énergétique

### Sources (2 jeux de données)

| Source | Période | Format | Volume |
|--------|---------|--------|--------|
| ADEME "nouveau" | post-juillet 2021 | API paginée JSON → CSV | ~14 M lignes |
| ADEME "ancien" | pré-juillet 2021 | API paginée JSON → CSV | ~10,7 M lignes |

### Téléchargement — `download_dpe.py`

Les DPE ne sont **pas disponibles en fichier direct** — ils sont servis par l'API ADEME data-fair via **pagination cursor-based** (10 000 lignes/requête).

**Processus :**
1. `GET /datasets/{id}/lines?size=10000&after={cursor}` en boucle
2. Écriture CSV au fil des pages (pas de chargement mémoire complet)
3. Colonnes sélectionnées uniquement (le dataset en contient ~200)
4. DPE ancien : filtre `dpe_vierge=0` et `est_efface=0` appliqués côté API

> Note : le DPE nouveau prend ~1-2h à télécharger (14M lignes × requêtes HTTP paginées)

```bash
python -m src.ingestion.download_dpe                   # les deux sources
python -m src.ingestion.download_dpe --source nouveau  # post-2021 uniquement
python -m src.ingestion.download_dpe --source ancien   # pré-2021 uniquement
```

### Traitement Spark — `spark_dpe.py`

1. Lecture des 2 CSV avec alignement des colonnes (noms différents entre sources)
2. Filtres DPE ancien : `dpe_vierge=0`, `est_efface=0`
3. Normalisation commune :
   - `classe_energie` → majuscule, trim, filtre A-G uniquement
   - `code_commune` → 5 chars (lpad)
   - `consommation_moyenne` → filtre 0–3000 kWh/m²/an (anomalies exclues)
4. **Union** `unionByName` des deux sources
5. Mise en cache Spark (évite de recalculer pour les 2 exports)
6. **Export 1** — diagnostics individuels (~18 M lignes) → `data/processed/dpe/diagnostics/`
7. **Export 2** — stats par commune (nb DPE, % par classe A-G, conso moyenne) → `data/processed/dpe/commune_stats/`

```bash
docker-compose run --rm processing python -m src.processing.spark_dpe
```

---

## 3. DVF — Demandes de Valeurs Foncières

### Sources (2 jeux de données)

| Source | Période | Format | Particularités |
|--------|---------|--------|----------------|
| **Geo-DVF** (Etalab) | 2020–2024 | CSV UTF-8, 1 fichier/an | Géolocalisé (lat/lon), `id_mutation` |
| **DVF brut** (DGFiP) | années hors Geo-DVF | `.txt.zip`, Latin-1, séparateur `\|` | Pas de géoloc, code commune sur 3 chars, date JJ/MM/AAAA |

### Téléchargement — `download_dvf.py`

**Geo-DVF Etalab :**
- URL directe par année : `geo-dvf/latest/csv/{year}/full.csv.gz`
- Télécharge en `.csv.gz` puis décompresse

**DVF DGFiP :**
- Interroge l'API data.gouv.fr pour trouver l'URL par titre de ressource (`"Valeurs foncières {year}"`)
- Télécharge l'archive `.txt.zip`, extrait le `.txt` interne
- Ne télécharge que les années **non couvertes** par Geo-DVF (évite les doublons)

```bash
python -m src.ingestion.download_dvf                    # tout
python -m src.ingestion.download_dvf --source geo       # Etalab uniquement
python -m src.ingestion.download_dvf --since 2022-01-01 # incrémental
```

### Traitement Spark — `spark_dvf.py`

1. Lecture avec **schémas explicites** (évite que `code_commune` "01001" soit lu comme entier)
2. Normalisation DGFiP :
   - Décimal virgule → point pour `valeur_fonciere`
   - Date `JJ/MM/AAAA` → `DateType`
   - `code_commune` = code_departement (2) + lpad(code_commune_court, 3) → 5 chars
   - Colonnes absentes (`id_mutation`, `longitude`, `latitude`) → `null`
3. Union des deux sources
4. Filtres : `nature_mutation = "Vente"` + `type_local in ("Maison", "Appartement")`
5. **Déduplication multi-lots** :
   - Geo-DVF : groupBy `id_mutation`, somme des surfaces
   - DGFiP : groupBy `(date, valeur, commune, type)`, somme des surfaces
6. Calcul `prix_m2 = valeur_fonciere / surface_reelle_bati`
7. Filtre anomalies : prix/m² entre 100 et 100 000 €, surface entre 5 et 10 000 m²
8. **Export Parquet partitionné par `annee`** → `data/processed/dvf/annee=YYYY/`

```bash
docker-compose run --rm processing python -m src.processing.spark_dvf
```

---

## Récapitulatif technique

| | BPE | DPE | DVF |
|--|-----|-----|-----|
| **Source** | data.gouv.fr API | API ADEME paginée | Etalab (direct) + data.gouv.fr API |
| **Format brut** | Parquet → CSV | JSON paginé → CSV | CSV.gz + txt.zip |
| **Librairies DL** | `requests`, `pandas` | `requests` | `requests`, `zipfile` |
| **Volume** | 1,8 M lignes | ~24 M lignes | ~25–30 M lignes |
| **Traitement** | PySpark | PySpark | PySpark |
| **Sortie** | Parquet (commune_stats) | Parquet (diagnostics + commune_stats) | Parquet partitionné par année |
| **Complexité notable** | Conversion Parquet→CSV | Pagination HTTP longue (~2h) | 2 formats hétérogènes, dédup multi-lots |
