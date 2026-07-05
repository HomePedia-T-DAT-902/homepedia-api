# Base de données Homepedia — Description des tables

Toutes les tables ci-dessous sont créées automatiquement par
[`src/database/postgres_schema.sql`](../src/database/postgres_schema.sql) au premier
démarrage de PostgreSQL — **sauf `city_reviews`**, créée à la volée par le loader
`ville_ideale` et le router `reviews` (voir plus bas).

## Tables de référence géographique

### `regions`
Contours et métadonnées des régions françaises.

| Colonne | Type | Description |
|---|---|---|
| `code_region` | VARCHAR(3) | Code région INSEE (PK) |
| `nom` | VARCHAR | Nom de la région |
| `geom` | GEOMETRY | Contour MultiPolygon (WGS-84) |

---

### `departements`
Contours et métadonnées des départements.

| Colonne | Type | Description |
|---|---|---|
| `code_departement` | VARCHAR(3) | Code département INSEE (PK) |
| `nom` | VARCHAR | Nom du département |
| `code_region` | VARCHAR(3) | FK → regions |
| `geom` | GEOMETRY | Contour MultiPolygon (WGS-84) |

---

### `communes`
Table de référence centrale — toutes les communes françaises (COG INSEE).

| Colonne | Type | Description |
|---|---|---|
| `code_commune` | VARCHAR(5) | Code INSEE 5 chars (PK) |
| `nom` | VARCHAR | Nom de la commune |
| `code_departement` | VARCHAR(3) | FK → departements |
| `code_region` | VARCHAR(3) | FK → regions |
| `code_postal` | VARCHAR(5) | Code postal principal |
| `population` | INTEGER | Population municipale |
| `superficie` | FLOAT | Superficie en km² |
| `densite` | FLOAT | Densité hab/km² |
| `latitude` / `longitude` | FLOAT | Centroïde de la commune |
| `geom` | GEOMETRY | Contour précis MultiPolygon |
| `geom_simplified` | GEOMETRY | Contour simplifié (affichage carte) |

---

### `iris_quartiers`
Découpage infra-communal IRIS (IGN) — environ 50 000 zones en France.

| Colonne | Type | Description |
|---|---|---|
| `code_iris` | VARCHAR(9) | Code IRIS (5 commune + 4 IRIS) (PK) |
| `code_commune` | VARCHAR(5) | FK → communes |
| `nom_iris` | VARCHAR | Nom du quartier IRIS |
| `type_iris` | CHAR(1) | H=habitat, A=activité, D=divers, Z=non découpé |
| `geom` | GEOMETRY | Contour MultiPolygon (WGS-84) |

**Usage API** : `GET /api/v1/geo/iris?bbox=...` ou `GET /api/v1/geo/communes/{code}/iris`

---

## Tables de faits immobiliers

### `dvf_transactions`
Transactions immobilières brutes (Demandes de Valeurs Foncières).
**Source** : Geo-DVF Etalab (géolocalisé) — une ligne = une vente.

| Colonne | Type | Description |
|---|---|---|
| `id` | SERIAL | PK auto-incrémenté |
| `id_mutation` | VARCHAR(20) | Identifiant mutation DVF |
| `code_commune` | VARCHAR(5) | FK → communes |
| `date_mutation` | DATE | Date de la vente |
| `nature_mutation` | VARCHAR | Type de mutation (Vente, etc.) |
| `type_local` | VARCHAR | Appartement, Maison, Local, Dépendance |
| `valeur_fonciere` | FLOAT | Prix total de la transaction (€) |
| `surface_reelle_bati` | FLOAT | Surface habitable (m²) |
| `nb_pieces` | INTEGER | Nombre de pièces principales |
| `surface_terrain` | FLOAT | Surface du terrain (m²) |
| `prix_m2` | FLOAT | Prix calculé au m² |
| `longitude` / `latitude` | FLOAT | Coordonnées GPS de la transaction |
| `geom` | GEOMETRY | Point PostGIS (WGS-84) |

**Usage API** : `GET /api/v1/prix/points?bbox=min_lon,min_lat,max_lon,max_lat`
→ Retourne les points agrégés par coordonnées (prix_m2_moyen + nb_transactions)

---

### `price_trends`
Prix médians pré-agrégés par commune × trimestre × type de bien.
**Calculé automatiquement** depuis `dvf_transactions` lors du load DVF.

| Colonne | Type | Description |
|---|---|---|
| `code_commune` | VARCHAR(5) | FK → communes (PK partielle) |
| `annee` | INTEGER | Année (PK partielle) |
| `trimestre` | INTEGER | Trimestre 1-4 (PK partielle) |
| `type_local` | VARCHAR | Appartement, Maison… (PK partielle) |
| `prix_median_m2` | FLOAT | Médiane des prix/m² sur la période |
| `nb_transactions` | INTEGER | Nombre de ventes sur la période |
| `variation_annuelle_pct` | FLOAT | Évolution vs même trimestre année N-1 (%) |

---

## Tables thématiques par commune

### `bpe_commune_stats`
Équipements et services par commune (Base Permanente des Équipements INSEE).
**Agrégation** : comptage des équipements par type depuis le fichier BPE (~2M lignes).

| Colonne | Type | Description |
|---|---|---|
| `code_commune` | VARCHAR(5) | FK → communes (PK) |
| `nb_equipements_total` | INTEGER | Total tous types confondus |
| `nb_a` | INTEGER | Enseignement (domaine A) |
| `nb_b` | INTEGER | Sport / Culture (domaine B) |
| `nb_c` | INTEGER | Commerce (domaine C) |
| `nb_d` | INTEGER | Santé (domaine D) |
| `nb_e` | INTEGER | Transport (domaine E) |
| `nb_f` | INTEGER | Tourisme (domaine F) |
| `nb_maternelles` | INTEGER | Écoles maternelles |
| `nb_primaires` | INTEGER | Écoles primaires |
| `nb_creches` | INTEGER | Crèches |
| `nb_colleges` | INTEGER | Collèges |
| `nb_lycees` | INTEGER | Lycées |
| `nb_medecins` | INTEGER | Médecins généralistes |
| `nb_pharmacies` | INTEGER | Pharmacies |
| `nb_urgences` | INTEGER | Urgences hospitalières |
| `nb_supermarches` | INTEGER | Supermarchés |
| `nb_hypermarches` | INTEGER | Hypermarchés |
| `nb_gares` | INTEGER | Gares |

**Usage API** : `GET /api/v1/equipements/{code_commune}`

---

### `securite_commune`
Données de délinquance communale (SSMSI).
**Agrégation** : 15 indicateurs regroupés en 5 catégories, agrégés par commune et année.

| Colonne | Type | Description |
|---|---|---|
| `code_commune` | VARCHAR(5) | FK → communes (PK partielle) |
| `annee` | INTEGER | Année (PK partielle) |
| `cambriolages_nombre` | INTEGER | Nb de cambriolages de logement |
| `cambriolages_pour_mille` | NUMERIC(6,1) | Taux pour 1 000 habitants |
| `violences_nombre` | INTEGER | Violences physiques (intrafamiliales + hors famille + sexuelles) |
| `violences_pour_mille` | NUMERIC(6,1) | Taux pour 1 000 habitants |
| `vols_nombre` | INTEGER | Vols (avec armes + sans violence + véhicules + accessoires) |
| `vols_pour_mille` | NUMERIC(6,1) | Taux pour 1 000 habitants |
| `stups_nombre` | INTEGER | Infractions stupéfiants (trafic + usage) |
| `stups_pour_mille` | NUMERIC(6,1) | Taux pour 1 000 habitants |
| `destructions_nombre` | INTEGER | Destructions et dégradations volontaires |
| `destructions_pour_mille` | NUMERIC(6,1) | Taux pour 1 000 habitants |

**Usage API** : `GET /api/v1/securite/{code_commune}`

---

### `education_commune`
Résultats du baccalauréat par commune (IVAL — lycées GT).
**Agrégation** : moyenne pondérée par le nombre de présentés sur tous les lycées de la commune.

| Colonne | Type | Description |
|---|---|---|
| `code_commune` | VARCHAR(5) | FK → communes (PK partielle) |
| `annee` | INTEGER | Année de la session bac (PK partielle) |
| `bac_presents` | INTEGER | Nombre total de candidats dans la commune |
| `bac_taux_reussite` | NUMERIC(5,1) | Taux de réussite moyen pondéré (%) |

**Usage API** : `GET /api/v1/education/{code_commune}`

---

### `commune_risques`
Risques naturels et technologiques par commune (API Géorisques).

| Colonne | Type | Description |
|---|---|---|
| `code_commune` | VARCHAR(5) | FK → communes (PK) |
| `inondation` | BOOLEAN | Exposition aux inondations |
| `seisme` | BOOLEAN | Zone sismique |
| `mouvement_terrain` | BOOLEAN | Risque de mouvement de terrain |
| `retrait_gonflement_argile` | BOOLEAN | Risque argile |
| `radon` | BOOLEAN | Présence de radon |
| `feu_foret` | BOOLEAN | Risque feux de forêt |
| `icpe` | BOOLEAN | Installation classée à proximité |
| `source_annee` | INTEGER | Année de la donnée source |

**Usage API** : `GET /api/v1/risques/{code_commune}` ou `GET /api/v1/risques?inondation=true`

---

### `risques_geopoints`
Points géolocalisés par type de risque (centroïde de la commune exposée) — pour l'affichage cartographique.

| Colonne | Type | Description |
|---|---|---|
| `id` | SERIAL | PK auto-incrémenté |
| `type_risque` | VARCHAR(50) | Type de risque (inondation, seisme, feu_foret…) |
| `longitude` / `latitude` | DOUBLE PRECISION | Coordonnées du point |
| `code_commune` | VARCHAR(5) | FK → communes |

**Usage API** : `GET /api/v1/risques/geopoints?bbox=...&type_risque=...`

---

### `commune_qualite_air`
Indice ATMO annuel par commune (ATMO France).

| Colonne | Type | Description |
|---|---|---|
| `code_commune` | VARCHAR(5) | FK → communes (PK) |
| `annee` | INTEGER | Année |
| `indice_atmo` | FLOAT | Indice ATMO moyen annuel (1=très bon, 6=très mauvais) |
| `nb_jours_bon` | INTEGER | Jours avec indice bon |
| `nb_jours_moyen` | INTEGER | Jours avec indice moyen |
| `nb_jours_degrade` | INTEGER | Jours avec indice dégradé |
| `nb_jours_mauvais` | INTEGER | Jours avec indice mauvais |
| `nb_jours_tres_mauvais` | INTEGER | Jours avec indice très mauvais |
| `nb_jours_extremement_mauvais` | INTEGER | Jours avec indice extrêmement mauvais |

**Usage API** : `GET /api/v1/qualite-air/{code_commune}`

---

### `city_reviews`
Avis citoyens sur les communes (ville-ideale.fr) — chargement à la demande.
**Non présente dans `postgres_schema.sql`** : la table est créée idempotemment (`CREATE TABLE IF NOT EXISTS`)
par le loader `ville_ideale` et par le router `reviews` lors du premier scraping.

| Colonne | Type | Description |
|---|---|---|
| `code_commune` | VARCHAR(5) | FK → communes (PK) |
| `note_globale` | FLOAT | Note globale /10 |
| `nb_avis` | INTEGER | Nombre d'avis |
| `notes` | JSONB | Notes par critère : environnement, transports, sécurité, santé, sports, culture, enseignement, commerces, qualité de vie |
| `word_cloud` | JSONB | Mots les plus fréquents dans les avis |
| `avis` | JSONB | Avis complets |
| `rang` | INTEGER | Classement national |
| `date_scraping` | DATE | Date du dernier scraping (TTL 30 jours) |

**Usage API** : `GET /api/v1/reviews/{code_commune}` (cache-first, scrape à la demande)
