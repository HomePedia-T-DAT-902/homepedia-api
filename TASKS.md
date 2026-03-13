# HOMEPEDIA -- Suivi des tâches

> **Projet** : T-DAT-902 | Plateforme d'analyse du marché immobilier français
> **Équipe** : 5 personnes | **Durée** : 3 mois
> **Légende taille** : S = Small (~2h) | M = Medium (~4h) | L = Large (~1j) | XL = Extra Large (~2j+)
> **Légende priorité** : P0 = Critique (bloquant) | P1 = Important | P2 = Secondaire

---

## Phase 0 : Setup & Infrastructure

- [ ] **P0-1** `S` `P0` -- Initialiser repo Git + `.gitignore` (data/, .env, __pycache__, .venv/, *.pyc, .DS_Store)
- [ ] **P0-2** `S` `P0` -- Créer `pyproject.toml` (Poetry) avec toutes les dépendances backend
  - pyspark, fastapi, uvicorn
  - scrapy, beautifulsoup4, requests, pandas, geopandas
  - sqlalchemy, psycopg2-binary, geoalchemy2
  - wordcloud, python-dotenv
  - Frontend (npm) : react, react-map-gl, mapbox-gl, recharts, @tanstack/react-query, tailwindcss
- [ ] **P0-3** `M` `P0` -- Créer `docker-compose.yml`
  - PostgreSQL 16 + PostGIS 3.4
  - Spark standalone : 1 master + 2 workers
  - Volumes persistants pour les données
- [ ] **P0-4** `S` `P0` -- Créer `.env.example` avec variables de connexion DB
- [ ] **P0-5** `L` `P0` -- Créer `src/database/postgres_schema.sql`
  - Tables de dimension : communes, departments, regions
  - Tables de faits : dvf_transactions, dpe_diagnostics, commune_statistics, commune_equipements, commune_criminalité
  - Tables analytiques : price_trends
  - Tables géospatiales (PostGIS) : geo_communes, geo_départements, geo_regions (GEOMETRY MultiPolygon 4326)
  - Tables JSONB : city_reviews (ratings, word_cloud, note_globale, nb_avis), listings (listing_data)
  - Index sur code_commune, date_mutation, type_local
  - Index GiST sur colonnes geometry (géospatial)
  - Index GIN sur colonnes JSONB (documents flexibles)
  - Index tsvector pour recherche full-text français sur les avis
- [ ] **P0-7** `M` `P1` -- Créer `Makefile` (targets: setup, ingest, process, load, api, frontend, update, all)
- [ ] **P0-8** `S` `P1` -- Écrire `README.md` (installation, lancement, architecture)
- [ ] **P0-9** `S` `P0` -- Créer l'arborescence des 2 repos : `homepedia-api` (src/ingestion, src/scraping, src/processing, src/database, src/api, data/raw, data/processed, tests) + `homepedia-front` (src/components, src/views, src/hooks, src/api, src/types, tests)

---

## Phase 1 : Ingestion des données [Semaines 2-3]

### Données gouvernementales (Open Data)

- [ ] **P1-1** `M` `P0` -- `src/ingestion/download_geo.py`
  - Télécharger le COG (Code Officiel Géographique) depuis geo.api.gouv.fr
  - Télécharger les GeoJSON des contours (communes, départements, régions) depuis data.gouv.fr
  - **Multi-fichiers** : 3-6 fichiers (1 par niveau géo × simplification : 5m, 50m, 100m)
  - Clé de jointure universelle : code_commune INSEE (5 caractères)
  - **Dépendance** : P0-9
- [ ] **P1-2** `L` `P0` -- `src/ingestion/download_dvf.py`
  - **Multi-fichiers (~12+)** : 2 sources distinctes à fusionner
    - Geo-DVF (Etalab) : 1 fichier/an 2020-2025, CSV UTF-8
    - DVF brut (DGFiP) : 1 fichier/an 2014-2019, CSV Latin-1, séparateur `|`
  - Support paramètre `--since YYYY-MM-DD` pour téléchargement incrémental
  - Volume total : ~8-10 GB, 25-30M lignes
  - **Dépendance** : P0-9
- [ ] **P1-3** `L` `P0` -- `src/ingestion/download_dpe.py`
  - **2 fichiers, formats incompatibles** :
    - DPE nouveau (post juillet 2021) : CSV, ~9M lignes
    - DPE ancien (pré-juillet 2021) : dump MySQL à convertir, ~10.7M lignes
  - Volume total : ~5-10 GB, ~20M lignes
  - **Dépendance** : P0-9
- [ ] **P1-4** `M` `P1` -- `src/ingestion/download_bpe.py`
  - Télécharger la Base Permanente des Équipements depuis INSEE
  - 229 types d'équipements (écoles, hôpitaux, gares, commerces...)
  - **1 fichier** (dernier millésime uniquement), ~2M lignes, ~150 MB
  - **Dépendance** : P0-9
- [ ] **P1-5** `M` `P1` -- `src/ingestion/download_insee.py`
  - Télécharger Filosofi (revenus/pauvreté par commune) : **1 XLSX**
  - Télécharger recensement (population par commune et année) : **1 XLSX** (1968-2023 intégré)
  - Télécharger données emploi/chômage (France Travail) : **1 CSV** (format long 2015-2024)
  - Volume total : ~120 MB (3 fichiers)
  - **Dépendance** : P0-9
- [ ] **P1-5b** `S` `P0` -- `src/ingestion/download_loyers.py`
  - **4 fichiers CSV** : 1 par type de bien (apparts, maisons, apparts 3+, apparts 1-2 pièces)
  - ~35K lignes/fichier, ~140K lignes au total
  - **Dépendance** : P0-9
- [ ] **P1-6** `S` `P1` -- `src/ingestion/download_crime.py`
  - Télécharger statistiques de criminalité depuis data.gouv.fr
  - **1 fichier** Parquet (format long : commune × année × indicateur, 2016-2025)
  - 14 indicateurs par commune, ~4.7M lignes
  - **Dépendance** : P0-9
- [ ] **P1-7** `S` `P1` -- `src/ingestion/download_education.py`
  - Télécharger DNB (brevet) + IVAL (lycées) depuis data.gouv.fr
  - **2 fichiers** CSV, 66 000+ établissements géolocalisés
  - Volume : ~30 MB
  - **Dépendance** : P0-9

### Données scrapées (non-tabulaires)

- [ ] **P1-8** `XL` `P1` -- `src/scraping/ville_ideale_scraper.py`
  - Scraper ville-ideale.fr : notes 8 critères + commentaires texte
  - ~8 500 villes, ~91 000 avis
  - Rate-limit strict : 1 requête/seconde, respect robots.txt
  - Stocker dans data/raw/ville_ideale/ en JSON
  - **Dépendance** : P0-9
- [ ] **P1-9** `L` `P2` -- `src/scraping/pap_scraper.py`
  - Scraper un échantillon d'annonces pap.fr (~5 000-10 000)
  - Extraire : prix, surface, localisation, type, description, DPE
  - Rate-limit strict, respect CGU
  - Stocker dans data/raw/pap/ en JSON
  - **Dépendance** : P0-9

---

## Phase 2 : Traitement Big Data (PySpark) [Semaines 3-5]

- [ ] **P2-1** `XL` `P0` -- `src/processing/spark_dvf.py`
  - Nettoyage DVF via PySpark :
    - Encodage Latin-1 -> UTF-8
    - Gestion valeurs manquantes (valeur_fonciere NaN)
    - Déduplication des mutations (plusieurs lignes par mutation)
    - Normalisation code_commune (padding 5 digits)
    - Calcul prix/m2 (valeur_fonciere / surface_reelle_bati)
    - Filtrage anomalies (prix négatifs, surfaces aberrantes)
  - Export en Parquet partitionné par année
  - **Dépendance** : P1-2
- [ ] **P2-2** `L` `P0` -- `src/processing/spark_dpe.py`
  - Nettoyage DPE via PySpark :
    - Normalisation des classes énergie (A-G)
    - Agrégation par commune (distribution des classes, consommation moyenne)
  - Export en Parquet
  - **Dépendance** : P1-3
- [ ] **P2-3** `XL` `P0` -- `src/processing/spark_aggregations.py`
  - Jointures multi-sources via PySpark/SparkSQL :
    - DVF + communes (ajout noms région/département, coordonnées)
    - BPE agrégé par commune (comptage par type d'équipement)
    - Price_trends : médiane prix/m2 par commune/trimestre/type_local, variation annuelle (YoY)
    - Stats communales : fusion revenu + pauvreté + emploi + population par commune+année
  - Tous les datasets traités via PySpark (uniformité, compatibilité machines hétérogènes)
  - **Dépendance** : P2-1, P2-2, P1-4, P1-5, P1-6, P1-7
- [ ] **P2-4** `M` `P1` -- `src/processing/spark_reviews.py`
  - Traitement basique des avis ville-ideale :
    - Agrégation des notes numériques (8 critères) par commune
    - Calcul note moyenne globale par commune
    - Comptage du nombre d'avis par commune
    - Calcul fréquences de mots basique (comptage simple, suppression stopwords français)
  - **Dépendance** : P1-8

---

## Phase 3 : Chargement en base [Semaine 5]

- [ ] **P3-1** `L` `P0` -- `src/database/postgres_loader.py`
  - Charger dans PostgreSQL :
    - Tables de dimension (communes, departments, regions) depuis COG
    - dvf_transactions depuis Parquet traité
    - dpe_diagnostics depuis Parquet traité
    - commune_statistics, commune_equipements, commune_criminalité
    - price_trends (table analytique pré-calculée)
  - Support UPSERT (INSERT ON CONFLICT UPDATE) pour mises à jour incrémentales
  - Création des index après chargement
  - **Dépendance** : P2-3, P0-5
- [ ] **P3-2** `L` `P1` -- Étendre `src/database/postgres_loader.py` (données PostGIS + JSONB)
  - Charger dans PostgreSQL :
    - geo_communes, geo_départements, geo_regions (GeoJSON via ST_GeomFromGeoJSON)
    - city_reviews (avis ville-ideale avec notes + fréquences mots en JSONB)
    - listings (annonces pap.fr en JSONB)
  - **Dépendance** : P2-3, P2-4, P0-5

---

## Phase 4 : API Backend (FastAPI) [Semaines 5-6]

- [ ] **P4-1** `M` `P0` -- `src/api/config.py` + `src/api/models/database.py`
  - Connexion PostgreSQL via SQLAlchemy + GeoAlchemy2 (async)
  - Chargement variables depuis .env
  - **Dépendance** : P3-1, P3-2
- [ ] **P4-2** `M` `P0` -- `src/api/routers/communes.py`
  - `GET /communes/{code}` -- fiche commune
  - `GET /communes/search?q=` -- recherche par nom
  - `GET /communes/{code}/details` -- fiche complète avec toutes les stats
  - **Dépendance** : P4-1
- [ ] **P4-3** `M` `P0` -- `src/api/routers/prices.py`
  - `GET /prices/{code_commune}?period=&type=` -- prix par commune
  - `GET /prices/trends/{code_departement}` -- tendances par département
  - **Dépendance** : P4-1
- [ ] **P4-4** `M` `P1` -- `src/api/routers/stats.py`
  - `GET /stats/{code_commune}` -- revenus, emploi, équipements, criminalité, DPE
  - **Dépendance** : P4-1
- [ ] **P4-5** `L` `P0` -- `src/api/routers/geo.py`
  - `GET /geo/communes?bbox=` -- GeoJSON communes via PostGIS (ST_AsGeoJSON, ST_Intersects)
  - `GET /geo/departments` -- GeoJSON départements via PostGIS
  - `GET /geo/choropleth?indicator=&level=` -- données choropleth par indicateur (JOIN PostGIS + tables analytiques)
  - **Dépendance** : P4-1
- [ ] **P4-6** `M` `P1` -- `src/api/routers/reviews.py`
  - `GET /reviews/{code_commune}` -- avis, notes moyennes (JSONB), fréquences mots (JSONB)
  - **Dépendance** : P4-1

---

## Phase 5 : Frontend React -- Single-page interactive [Semaines 5-7]

> **Architecture** : une page unique interactive centrée sur la carte (pas de multi-pages).
> Navigation par viewLevel (national → region → departement → commune) via clic carte + recherche.

### Setup et composants réutilisables (peuvent démarrer en parallèle de Phase 4)

- [ ] **P5-0** `S` `P0` -- Init projet React avec Vite + TypeScript
  - `npm create vite@latest frontend -- --template react-ts`
  - Installer : react-map-gl, mapbox-gl, recharts, @tanstack/react-query, tailwindcss
  - Config proxy Vite vers FastAPI (dev)
  - **PAS de react-router-dom** (single-page interactive)
- [ ] **P5-1** `M` `P0` -- `src/components/Layout.tsx`
  - Navbar (logo, barre de recherche autocomplete, filtres), footer
  - Structure responsive : carte à gauche, panneau latéral à droite
- [ ] **P5-2** `L` `P0` -- `src/components/MapView.tsx`
  - Carte choropleth (react-map-gl + Mapbox GL JS) -- coloration par indicateur via fill layers
  - Carte bubble map -- cercles proportionnels via circle layers
  - Gestion du zoom animé lors des transitions de viewLevel
  - `onFeatureClick` → déclenche la navigation (navigateTo)
  - Composant réutilisable paramétrable (indicateur, niveau géo, palette)
- [ ] **P5-3** `L` `P0` -- `src/components/Charts.tsx`
  - LineChart (tendances temporelles)
  - BarChart (comparaisons, distributions)
  - RadarChart (profil multi-critères)
  - BoxPlot (distribution des prix via customisation Recharts)
  - Tous via Recharts, paramétrables
- [ ] **P5-4** `M` `P0` -- `src/components/SidePanel.tsx`
  - Panneau latéral contextuel qui s'adapte au viewLevel :
    - national → KPIs nationaux, top/flop, tendance
    - region → KPIs régionaux, comparaison départements
    - departement → classement communes, tendances départementales
    - commune → fiche détaillée avec onglets (Prix, DPE, Équipements, Revenus, Criminalité, Avis)
  - **Dépendance** : P5-3
- [ ] **P5-5** `M` `P1` -- `src/components/Filters.tsx` + `Breadcrumb.tsx`
  - Barre de filtres horizontale : indicateur choroplèthe, type de bien, période (slider)
  - Breadcrumb cliquable (France > Région > Département > Commune)
  - Gestion d'état via React Context (FilterProvider)
- [ ] **P5-6** `S` `P1` -- `src/assets/` + Tailwind config
  - Thème Tailwind custom (couleurs, typographie, espacements)
  - Responsive design

### Application et intégration

- [ ] **P5-7** `M` `P0` -- `src/App.tsx` + Providers
  - FilterProvider (filtres globaux : indicateur, type bien, période)
  - MapNavigationProvider (viewLevel, selectedCode, zoom, breadcrumb)
  - Layout global avec carte + panneau latéral
  - **Dépendance** : P5-0, P5-1
- [ ] **P5-8** `M` `P0` -- `src/hooks/useMapNavigation.ts`
  - Context pour la navigation carte (viewLevel, selectedCode, parentCodes)
  - Fonctions : navigateTo(level, code), goBack(), goToNational()
  - Transitions animées (zoom) lors du changement de viewLevel
  - **Dépendance** : P5-7
- [ ] **P5-9** `M` `P0` -- `src/hooks/` + `src/api/`
  - Custom hooks pour le data fetching (useCommune, usePrices, useStats, useGeo, useReviews)
  - Client API centralisé (fetchApi, fetchGeoJson)
  - useFilters (FilterProvider)
  - **Dépendance** : P5-7
- [ ] **P5-10** `L` `P0` -- Intégration viewLevel national + region
  - Choroplèthe départements colorée par indicateur
  - SidePanel national : KPIs, top/flop, tendance
  - SidePanel region : comparaison départements, tendances
  - Clic département → zoom + transition vers region/departement
  - **Dépendance** : P4-5, P5-2, P5-3, P5-4, P5-8
- [ ] **P5-11** `L` `P0` -- Intégration viewLevel departement
  - Carte communes (bubble map ou choroplèthe)
  - SidePanel : classement communes triable, tendances départementales
  - Clic commune → zoom + transition vers commune
  - **Dépendance** : P4-5, P5-2, P5-3, P5-4, P5-8
- [ ] **P5-12** `XL` `P0` -- Intégration viewLevel commune (fiche détaillée)
  - SidePanel avec onglets :
    - Prix immobilier (historique + tendance + distribution)
    - DPE (distribution des classes énergétiques)
    - Équipements et services (nombre par catégorie)
    - Revenus et emploi
    - Criminalité
    - Avis habitants (notes + word cloud basique)
  - **Dépendance** : P4-2, P4-3, P4-4, P4-6, P5-3, P5-4, P5-8
- [ ] **P5-13** `M` `P1` -- `src/components/WordCloud.tsx`
  - Word cloud basique (fréquence de mots, pas de sentiment)
  - Intégré dans l'onglet "Avis" du SidePanel commune
  - **Dépendance** : P4-6, P5-12
- [ ] **P5-14** `M` `P1` -- `src/views/TendancesView.tsx`
  - Mode tendances (viewMode=tendances via navbar)
  - Comparaison multi-communes : sélection 2-5 communes, LineChart multi-séries
  - **Dépendance** : P5-3, P5-8, P5-9
- [ ] **P5-15** `M` `P1` -- `src/views/ComparaisonView.tsx`
  - Mode comparaison (viewMode=comparaison via navbar)
  - Sélection 2-4 communes, RadarChart multi-critères, table side-by-side
  - **Dépendance** : P5-3, P5-8, P5-9
- [ ] **P5-16** `M` `P1` -- `src/views/EnergieView.tsx`
  - Mode énergie (viewMode=energie via navbar)
  - Carte heatmap DPE par département, distribution classes A-G, évolution temporelle
  - **Dépendance** : P5-2, P5-3, P5-8
- [ ] **P5-17** `M` `P1` -- `src/views/AvisView.tsx`
  - Mode avis (viewMode=avis via navbar)
  - Recherche commune, WordCloud, RadarChart 8 critères, choropleth note globale
  - **Dépendance** : P5-8, P5-13

---

## Phase 6 : Finalisation [Semaines 7-8]

- [ ] **P6-1** `L` `P1` -- Tests unitaires
  - Tests ingestion (download + parsing)
  - Tests processing (transformations PySpark)
  - Tests API (endpoints FastAPI)
  - **Dépendance** : Phases 1-4
- [ ] **P6-2** `L` `P1` -- Tests d'intégration
  - Pipeline complet : raw -> process -> load -> API -> frontend
  - **Dépendance** : Tout
- [ ] **P6-3** `M` `P1` -- Documentation méthodologie de nettoyage des données
  - **Dépendance** : Phase 2
- [ ] **P6-4** `M` `P1` -- Documentation schéma de base de données
  - **Dépendance** : Phase 3
- [ ] **P6-5** `S` `P2` -- Documentation traitement des avis
  - **Dépendance** : P2-4
- [ ] **P6-6** `L` `P1` -- Optimisation des performances
  - Cache API (Redis ou in-memory)
  - Pagination API
  - Optimisation index SQL
  - **Dépendance** : Phases 4-5
- [ ] **P6-7** `M` `P0` -- Docker final : `docker-compose up` lance tout (DB + Spark + API + Frontend)
  - **Dépendance** : Tout
- [ ] **P6-8** `M` `P2` -- `src/ingestion/update_all.py` : script de mise à jour incrémentale (`--since`)
  - **Dépendance** : Phase 1
- [ ] **P6-9** `M` `P2` -- `docs/architecture_scalabilite.md`
  - Architecture cible : Airflow DAGs, Kafka streaming
  - Schéma de scalabilité pour la soutenance

---

## Bonus (optionnels, si temps restant)

- [ ] **B-1** `M` `P2` -- Authentification JWT (FastAPI)
- [ ] **B-2** `L` `P2` -- Déploiement en ligne (à définir)
- [ ] **B-3** `L` `P2` -- Vue admin serveur (monitoring cluster Spark)
- [ ] **B-4** `M` `P2` -- Mises à jour temps réel (scheduler APScheduler)
- [ ] **B-5** `S` `P2` -- Visite guidée de l'application
- [ ] **B-6** `XL` `P2` -- Extension à d'autres pays
- [ ] **B-7** `XL` `P2` -- Pipeline NLP avancé sur les avis ville-ideale
  - spaCy `fr_core_news_md` : tokenisation, lemmatisation
  - Analyse de sentiment (positif/négatif) par commentaire (CamemBERT ou TextBlob-fr)
  - Extraction de thèmes récurrents
  - Word cloud enrichi (mots positifs vs négatifs)

---

## Diagramme de dépendances

```
Phase 0 (Setup)
  |
  v
Phase 1 (Ingestion) --------+
  |                          |
  v                          v
Phase 2 (Processing)    Phase 5 (Setup React + Composants : P5-0 a P5-6)
  |                          |
  v                          |
Phase 3 (Loading)            |
  |                          |
  v                          v
Phase 4 (API) ---------> Phase 5 (App + viewLevels : P5-7 a P5-13)
  |                          |
  v                          v
Phase 6 (Finalisation + Tests + Docs)
```
