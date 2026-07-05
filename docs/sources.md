# Sources de données — Homepedia

Ce document décrit **uniquement les sources réellement intégrées** au pipeline
([`src/pipeline.py`](../src/pipeline.py)). Chaque source est un dossier autonome dans
[`src/sources/`](../src/sources/) qui implémente l'interface `DataSource`
(`download → preprocess → process → load`).

**Clé de jointure universelle** : `code_commune` (code INSEE, 5 caractères).

## Vue d'ensemble

| Source | Clé pipeline | Fournisseur | Contenu | Table(s) PostgreSQL |
|--------|-------------|-------------|---------|---------------------|
| Géographie | `geo` | Etalab / data.gouv.fr / INSEE | Contours + métadonnées communes, départements, régions + population | `regions`, `departements`, `communes` |
| Équipements | `bpe` | INSEE (data.gouv.fr) | Base Permanente des Équipements (écoles, santé, commerces…) | `bpe_commune_stats` |
| Transactions | `dvf` | DGFiP / Etalab (geo-dvf) | Demandes de Valeurs Foncières 2020-2025 | `dvf_transactions`, `price_trends` |
| IRIS | `iris` | IGN (Géoplateforme WFS) | Contours des quartiers infra-communaux | `iris_quartiers` |
| Avis | `ville_ideale` | ville-ideale.fr (scraping) | Notes et avis citoyens par commune | `city_reviews` |
| Sécurité | `crime` | SSMSI (data.gouv.fr) | Délinquance communale (15 indicateurs → 5 catégories) | `securite_commune` |
| Éducation | `education` | MENJ — IVAL (data.gouv.fr) | Résultats du bac par commune (lycées GT) | `education_commune` |
| Risques | `risques` | Géorisques (API BRGM) | Risques naturels et technologiques + géopoints | `commune_risques`, `risques_geopoints` |
| Qualité de l'air | `qualite_air` | ATMO France (data.gouv.fr) | Indice ATMO annuel par commune | `commune_qualite_air` |

---

## `geo` — Géographie de référence

**Fournisseur** : Etalab (contours), data.gouv.fr (CSV communes), INSEE (population).
**Rôle** : source socle — elle crée les tables `communes` / `departements` / `regions`
qui servent de référentiel à toutes les autres (contrôle de clé étrangère sur `code_commune`).

Fichiers téléchargés :

- Contours administratifs 2025 (GeoJSON) : `communes-5m`, `communes-50m`, `departements-5m`, `regions-5m`
  — base `https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/geojson`
- CSV communes de France 2025 (`code_insee`, `nom_standard`, `dep_code`, `reg_code`)
- Population municipale INSEE (`xlsx`)

Volume : ~35 000 communes.

---

## `bpe` — Base Permanente des Équipements

**Fournisseur** : INSEE via l'API data.gouv.fr (`dataset_id` `69ca8e301e273a3a7f32ee61`).
**Contenu** : recensement des équipements et services (enseignement, sport/culture,
commerce, santé, transport, tourisme). Agrégé par commune au chargement.

Le comptage produit un total, un sous-total par grande catégorie (`A`-`F`) et des
compteurs pour les types clés (maternelles, collèges, médecins, pharmacies, gares…).

Volume : ~1,8 M lignes.

---

## `dvf` — Demandes de Valeurs Foncières

**Fournisseur** : DGFiP, deux origines croisées :

- **geo-dvf Etalab** (géolocalisé) : `https://files.data.gouv.fr/geo-dvf/latest/csv`, années 2020-2024
- **DGFiP brut** (`dataset_id` `5c4ae55a634f4117716d5656`), années 2020-2025

**Contenu** : chaque transaction immobilière (prix, surface, type de bien, localisation).
Le `process` filtre les valeurs aberrantes (prix/m², surface, prix minimum) et calcule
le `prix_m2`. Le `load` pré-agrège les prix médians par commune × trimestre × type de bien
dans `price_trends`.

Volume : ~10 M lignes. **Source la plus lourde** (plusieurs Go).

---

## `iris` — Contours IRIS

**Fournisseur** : IGN — Géoplateforme WFS (`https://data.geopf.fr/wfs/ows`,
couche `STATISTICALUNITS.IRIS:contours_iris`), pagination par 5 000.
**Contenu** : découpage infra-communal (quartiers) pour l'affichage cartographique fin.

Volume : ~49 000 polygones.

---

## `ville_ideale` — Avis citoyens (scraping)

**Fournisseur** : ville-ideale.fr, récupéré via un **spider Scrapy**
([`src/sources/ville_ideale/scraper/`](../src/sources/ville_ideale/scraper/)).
**Contenu** : note globale, notes par critère (environnement, transports, sécurité,
santé, sports/loisirs, culture, enseignement, commerces, qualité de vie), avis textuels,
nuage de mots.

Le `process` applique un traitement NLP léger (tokenisation + stop-words FR en
bibliothèque standard, sans dépendance externe) pour produire le nuage de mots.

**Chargement à la demande** : l'API sert les avis *cache-first* depuis `city_reviews`
et scrape une commune absente/périmée au vol
([`src/sources/ville_ideale/on_demand.py`](../src/sources/ville_ideale/on_demand.py)).

---

## `crime` — Délinquance communale

**Fournisseur** : SSMSI (Service statistique ministériel de la sécurité intérieure)
via data.gouv.fr — bases statistiques communales de la délinquance.
**Contenu** : 15 indicateurs regroupés en 5 catégories — cambriolages, violences, vols,
stupéfiants, destructions. Agrégés par commune et par année, avec taux pour 1 000 habitants.

---

## `education` — Résultats du baccalauréat

**Fournisseur** : MENJ — indicateurs IVAL (Indicateurs de Valeur Ajoutée des Lycées),
bac général et technologique, via data.gouv.fr.
**Contenu** : nombre de présentés et taux de réussite. Agrégé par commune (moyenne
pondérée par le nombre de présentés sur les lycées de la commune).

---

## `risques` — Risques naturels et technologiques

**Fournisseur** : API Géorisques (BRGM), plusieurs endpoints
(`gaspar/risques`, `mvt`, `cavites`, `installations_classees`).
**Contenu** :

- Par commune : exposition (booléens) aux inondations, séismes, mouvements de terrain,
  retrait-gonflement des argiles, radon, feux de forêt, ICPE → `commune_risques`
- Géopoints : points géolocalisés par type de risque → `risques_geopoints`

Le module dédié [`download_geopoints.py`](../src/sources/risques/download_geopoints.py)
récupère les points cartographiques exposés par `GET /api/v1/risques/geopoints`.

---

## `qualite_air` — Indice ATMO

**Fournisseur** : ATMO France — dataset « Indice ATMO France » sur data.gouv.fr
(`dataset_id` `6149925a2ff0ab6cebdd6fe8`).
**Contenu** : indice ATMO moyen annuel par commune et répartition du nombre de jours par
niveau de qualité (bon → extrêmement mauvais).

---

## Ajouter une nouvelle source

1. Créer `src/sources/<nom>/` avec `config.py`, `download.py`, `preprocess.py`,
   `process.py`, `load.py`, `source.py`.
2. Faire hériter `source.py` de `DataSource` ([`src/sources/base.py`](../src/sources/base.py))
   et implémenter les 4 étapes.
3. Enregistrer la source dans le dictionnaire `SOURCES` de
   [`src/pipeline.py`](../src/pipeline.py) — une seule ligne.

La source est alors automatiquement prise en compte par `make pipeline` et
`python -m src.pipeline run-all`.
