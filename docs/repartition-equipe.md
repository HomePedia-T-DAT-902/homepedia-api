# Homepedia — Répartition de l'équipe

> **Projet** : T-DAT-902 | 5 membres | 3 mois
> **Principe** : chaque membre possède un pipeline vertical pour minimiser les dépendances.

---

## Vue d'ensemble

| Membre     | Contrainte            | Rôle assigné                                                                                       |
| ---------- | --------------------- | -------------------------------------------------------------------------------------------------- |
| **A**      | Front uniquement      | Frontend : composants + carte + navigation + intégration                                           |
| **B**      | Back uniquement       | Schema SQL + API FastAPI complète + tests/optim API                                                |
| **C**      | Data/Spark uniquement | Pipeline lourd : ingestion DVF/DPE/GeoJSON + Spark DVF/DPE + loading principal                     |
| **D**      | Data/Spark + flexible | Pipeline complémentaire : ingestion stats + scraping + Spark agrégations/reviews + loading PostGIS |
| **Marine** | Polyvalente           | Infra Docker + frontend commune/vues spécialisées + docs + coordination                            |

---

## Membre A — Frontend composants + navigation

> Ne touche qu'au front. Peut démarrer dès la semaine 1.

| Tâche | Description                                             | Taille |
| ----- | ------------------------------------------------------- | ------ |
| P5-0  | Init Vite + TS + dépendances                            | S      |
| P5-1  | Layout.tsx (navbar, recherche, structure responsive)    | M      |
| P5-2  | MapView.tsx (carte choropleth/bubble, react-map-gl)     | L      |
| P5-3  | Charts.tsx (LineChart, BarChart, RadarChart, BoxPlot)   | L      |
| P5-4  | SidePanel.tsx (panneau contextuel par viewLevel)        | M      |
| P5-5  | Filters.tsx + Breadcrumb.tsx                            | M      |
| P5-6  | Assets + Tailwind config                                | S      |
| P5-7  | App.tsx + Providers                                     | M      |
| P5-8  | useMapNavigation.ts                                     | M      |
| P5-9  | Hooks + API client (useCommune, usePrices, fetchApi...) | M      |
| P5-10 | Intégration viewLevel national + region                 | L      |
| P5-11 | Intégration viewLevel département                       | L      |

**Charge estimée : ~10 jours**

> Bloqué par l'API à partir de P5-10 → peut mocker les données en attendant.

---

## Membre B — Backend API + Schema SQL

> Ne touche qu'au back. Commence par le schema SQL (semaine 1), puis API dès que le loading est fait.

| Tâche | Description                                               | Taille |
| ----- | --------------------------------------------------------- | ------ |
| P0-5  | Schema SQL complet (tables, index GiST/GIN/tsvector)      | L      |
| P4-1  | Config SQLAlchemy async + GeoAlchemy2 + .env              | M      |
| P4-2  | routers/communes.py (recherche, fiche)                    | M      |
| P4-3  | routers/prices.py (prix, tendances)                       | M      |
| P4-4  | routers/stats.py (revenus, emploi, DPE, crime, éducation) | M      |
| P4-5  | routers/geo.py (GeoJSON, choropleth PostGIS)              | L      |
| P4-6  | routers/reviews.py (avis JSONB, notes, word cloud)        | M      |
| P6-4  | Documentation schema de base de données                   | M      |
| P6-6  | Optimisation performances (cache, pagination, index)      | L      |
| P6-1  | Tests unitaires API (sa partie)                           | M      |

**Charge estimée : ~10 jours**

> Bloqué en semaines 2-4 → en profiter pour écrire les modèles SQLAlchemy/Pydantic et préparer les tests avec fixtures.

---

## Membre C — Pipeline Data lourd (DVF + DPE)

> Data/Spark uniquement. Les 2 plus gros datasets du projet.

| Tâche | Description                                                  | Taille |
| ----- | ------------------------------------------------------------ | ------ |
| P1-2  | download_dvf.py (~12 fichiers, 2 formats, 25-30M lignes)     | L      |
| P1-3  | download_dpe.py (2 formats incompatibles, ~20M lignes)       | L      |
| P1-1  | download_geo.py (COG + contours GeoJSON)                     | M      |
| P1-4  | download_bpe.py (équipements, 2M lignes)                     | M      |
| P2-1  | spark_dvf.py (nettoyage, dédup, prix/m², anomalies)          | XL     |
| P2-2  | spark_dpe.py (normalisation classes, agrégation commune)     | L      |
| P3-1  | postgres_loader.py — tables dimension + faits + price_trends | L      |
| P6-1  | Tests unitaires ingestion + processing (sa partie)           | M      |

Ajout cadastre

**Charge estimée : ~10-11 jours**

> Pipeline critique. Commence dès semaine 2.

---

## Membre D — Pipeline Data complémentaire + Scraping

> Data/Spark + flexible. Sources plus petites mais plus nombreuses + scraping.

| Tâche         | Description                                                          | Taille |
| ------------- | -------------------------------------------------------------------- | ------ |
| P1-5          | download_insee.py (Filosofi, population, emploi)                     | M      |
| P1-5b         | download_loyers.py (4 CSV)                                           | S      |
| P1-6          | download_crime.py (Parquet, 4.7M lignes)                             | S      |
| P1-7          | download_education.py (DNB + IVAL)                                   | S      |
| P1-8          | ville_ideale_scraper.py (~91K avis, rate-limited)                    | XL     |
| P1-9          | pap_scraper.py (~5-10K annonces)                                     | L      |
| P2-3          | spark_aggregations.py (jointures multi-sources, price_trends, stats) | XL     |
| P2-4          | spark_reviews.py (agrégation notes, fréquences mots)                 | M      |
| P3-2          | postgres_loader — PostGIS + JSONB (GeoJSON, avis, annonces)          | L      |
| P1-10 à P1-17 | Sources complémentaires (selon temps disponible)                     | ~3-4j  |

**Charge estimée : ~10-12 jours**

> Le scraping (P1-8) est long mais passif : une fois lancé, il tourne en fond.

---

## Marine — Infra + Frontend commune + Vues + Docs + Coordination

> Rôle de coordination : tout ce qui relie les morceaux + la partie la plus complexe du frontend.

| Tâche        | Description                                           | Taille |
| ------------ | ----------------------------------------------------- | ------ |
| **Infra**    |                                                       |        |
| P0-1         | Init repos Git + .gitignore                           | S      |
| P0-2         | pyproject.toml (Poetry)                               | S      |
| P0-3         | docker-compose.yml (PostgreSQL + Spark)               | M      |
| P0-4         | .env.example                                          | S      |
| P0-7         | Makefile                                              | M      |
| P0-9         | Arborescence des 2 repos                              | S      |
| P6-7         | Docker final (tout lance avec docker-compose up)      | M      |
| **Frontend** |                                                       |        |
| P5-12        | Fiche commune détaillée (onglets prix, DPE, équip...) | XL     |
| P5-13        | WordCloud.tsx                                         | M      |
| P5-14        | TendancesView.tsx (comparaison multi-communes)        | M      |
| P5-15        | ComparaisonView.tsx (radar multi-critères)            | M      |
| P5-16        | EnergieView.tsx (carte DPE)                           | M      |
| P5-17        | AvisView.tsx (word cloud + radar notes)               | M      |
| **Docs**     |                                                       |        |
| P0-8         | README.md                                             | S      |
| P6-3         | Doc méthodologie nettoyage                            | M      |
| P6-9         | Doc architecture scalabilité                          | M      |

**Charge estimée : ~11-12 jours**

> Infra en semaine 1 (débloque tout le monde), puis frontend en semaines 5-7.

---

## Timeline

```
         Sem 1        Sem 2-3          Sem 3-5          Sem 5         Sem 5-6        Sem 7-8
         ─────        ───────          ───────          ────          ───────        ───────
A (front) P5-0→P5-6   P5-7→P5-9       (mock API)       ─────────── P5-10, P5-11 ───────────→
B (back)  P0-5         modèles/tests   (attend loading) P4-1        P4-2→P4-6      P6-4, P6-6
C (data)  ─────────── P1-2, P1-3, P1-1, P1-4 ────────→ P2-1, P2-2  P3-1           tests
D (data)  ─────────── P1-5→P1-7, P1-8, P1-9 ─────────→ P2-3, P2-4  P3-2           compléments
Marine    P0-*, infra  coordination                     ─────────── P5-12→P5-17 ──→ P6-7, docs
```

---

## Points d'attention

1. **B est bloqué en semaines 2-4** en attendant les données chargées en base. Il peut occuper ce temps en écrivant le schema SQL, les modèles SQLAlchemy/Pydantic, et les tests avec des fixtures.

2. **A peut mocker l'API** en attendant que B ait fini les routers : données en dur ou mock JSON pour développer les composants.

3. **P2-3 (spark_aggregations) est le point de coordination C↔D** : C fournit les Parquet DVF/DPE, D fait les jointures multi-sources. Bien définir le format Parquet attendu ensemble.

4. **Marine débloque tout le monde en semaine 1** (repos, Docker, Makefile) puis passe en mode frontend + docs.

5. **En semaines 6-7, les membres C et D sont libérés** de leur pipeline → ils peuvent aider sur les tests (P6-1, P6-2) et la documentation.

---

## Comment les données sont récupérées

### Mode d'acquisition

| Mode                              | Sources concernées                                                                                                                             |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Téléchargement fichier (HTTP)** | DVF, DPE, BPE, INSEE, loyers, crime, éducation, GeoJSON, LOVAC, zonage, REI, internet, ensoleillement, eau, RPLS, comptes, navettes, politique |
| **API REST**                      | Géorisques uniquement (1 appel/commune, ~35K appels batch)                                                                                     |
| **Scraping HTML**                 | ville-ideale.fr (Scrapy), pap.fr (BeautifulSoup)                                                                                               |

> **90% des sources sont des fichiers à télécharger** via une URL directe. Ce n'est pas un flux continu : on télécharge une fois, on traite, on charge en base.

### Fréquence de mise à jour des sources

| Source                       | MAJ côté fournisseur            | Impact pour nous                |
| ---------------------------- | ------------------------------- | ------------------------------- |
| DVF                          | Semestrielle (avril + octobre)  | Nouveaux fichiers annuels       |
| DPE                          | Continue (~35K entrées/semaine) | Le CSV grossit en permanence    |
| BPE, loyers, GeoJSON         | Annuelle                        | Remplace le précédent           |
| INSEE (Filosofi, population) | Annuelle                        | Nouveau fichier                 |
| France Travail               | Trimestrielle                   | Nouvelles lignes ajoutées       |
| Criminalité                  | Annuelle                        | Nouvelles lignes ajoutées       |
| Scraping                     | Quand on le relance             | Données fraîches à chaque run   |
| Géorisques                   | Temps réel (API)                | Données fraîches à chaque appel |
