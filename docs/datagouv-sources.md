# Sources de données — Homepedia

> Inventaire des datasets pour l'analyse du marché immobilier français.
> Document de référence pour l'équipe — à consulter avant toute implémentation.

## Légende

| Badge | Signification |
|-------|---------------|
| `P0` | **Obligatoire** — coeur du projet, bloquant si absent |
| `P1` | **Forte valeur** — enrichit significativement l'analyse |
| `P2` | **Optionnel** — si le temps le permet |
| `EXCLU` | Écarté (obsolète, redondant, granularité inadaptée) |
| `✅` | Colonnes vérifiées sur fichier réel |
| `⬜` | À vérifier lors du téléchargement |

**Clé de jointure universelle** : `code_commune` INSEE (5 caractères).

---

## 1. Données immobilières

### DVF — Demandes de Valeurs Foncières · `P0` `✅`

- **Source** : DGFiP — **Explorateur** : https://explore.data.gouv.fr/immobilier
- **Contenu** : Transactions immobilières (ventes) — prix, surface, type de bien, localisation
- **Volume** : ~25-30M lignes — **Format** : CSV — **MAJ** : semestrielle (avril et octobre)
- **Granularité** : parcelle cadastrale (agrégeable par commune via `code_commune`)
- **Exclut** : Alsace-Moselle (régime foncier différent) et Mayotte
- **Tâche** : P1-2, P2-1

| Version | Lien | Période | Particularité |
|---------|------|---------|---------------|
| **DVF brut** (DGFiP) | https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres | 2014 — 2025 | Encodage Latin-1, pas de géolocalisation, colonnes brutes |
| **Geo-DVF** (Etalab) | https://files.data.gouv.fr/geo-dvf/latest/csv/ | **2020 — 2025 uniquement** | UTF-8, géolocalisé (longitude/latitude), colonnes normalisées |

> **Attention** : Geo-DVF ne couvre que 2020-2025. Pour 2014-2019, il faut utiliser le DVF brut.

#### Colonnes Geo-DVF (vérifiées sur `full.csv.gz`)

| Colonne | Description | Utilisée dans Homepedia |
|---------|-------------|------------------------|
| `id_mutation` | Identifiant unique de la mutation | Oui (déduplication multi-lots) |
| `date_mutation` | Date au format ISO-8601 | Oui |
| `numero_disposition` | Numéro de disposition | Non |
| `nature_mutation` | "Vente", "Adjudication", "Échange", "Expropriation" | Oui (filtre sur "Vente") |
| `valeur_fonciere` | Prix en EUR (séparateur décimal = point) | Oui |
| `adresse_numero` | Numéro de voie | Non |
| `adresse_suffixe` | Suffixe (bis, ter...) | Non |
| `adresse_nom_voie` | Nom de la voie | Non |
| `adresse_code_voie` | Code voie | Non |
| `code_postal` | Code postal | Non (redondant) |
| `code_commune` | Code commune INSEE (5 chars) | Oui (clé de jointure) |
| `nom_commune` | Nom de la commune | Non (redondant avec table communes) |
| `code_departement` | Code département | Non (redondant) |
| `ancien_code_commune` | Code avant fusion | Non (utile si gestion historique) |
| `ancien_nom_commune` | Nom avant fusion | Non |
| `id_parcelle` | Identifiant cadastral (14 chars) | Non |
| `ancien_id_parcelle` | Ancien identifiant parcelle | Non |
| `numero_volume` | Numéro de volume | Non |
| `lot1_numero` à `lot5_numero` | Numéros de lots (**sans underscore**) | Non |
| `lot1_surface_carrez` à `lot5_surface_carrez` | Surfaces Carrez par lot (**sans underscore**) | Non |
| `nombre_lots` | Nombre total de lots | Non |
| `code_type_local` | Code numérique du type | Non |
| `type_local` | "Maison", "Appartement", "Dépendance", "Local industriel. commercial ou assimilé" | Oui (filtre Maison/Appartement) |
| `surface_reelle_bati` | Surface en m² | Oui |
| `nombre_pieces_principales` | Nombre de pièces | Oui |
| `code_nature_culture` | Code type de terrain | Non |
| `nature_culture` | "terres", "prés", "vignes", etc. | Non |
| `code_nature_culture_speciale` | Code culture spéciale | Non |
| `nature_culture_speciale` | Culture spéciale | Non |
| `surface_terrain` | Surface terrain en m² | Oui |
| `longitude` | Coordonnée WGS-84 | Oui (clic bâtiment sur carte) |
| `latitude` | Coordonnée WGS-84 | Oui (clic bâtiment sur carte) |

> **Total** : 39 colonnes dans Geo-DVF (CSV séparé par virgules, UTF-8). Homepedia en retient ~10 + calcule `prix_m2`.
> Les coordonnées `longitude`/`latitude` permettent l'**affichage individuel des transactions sur la carte** (clic sur un bâtiment/immeuble pour voir les ventes associées).

#### Colonnes DVF brut (vérifiées sur `valeursfoncieres-2025-s1.txt`)

> **Attention** : format différent de Geo-DVF — séparateur `|`, encodage Latin-1, pas de géolocalisation.

| Colonne brute | Équivalent Geo-DVF | Notes |
|---------------|-------------------|-------|
| `Identifiant de document` | *(absent)* | ID interne DGFiP |
| `Reference document` | *(absent)* | |
| `1 Articles CGI` à `5 Articles CGI` | *(absent)* | Articles du CGI |
| `No disposition` | `numero_disposition` | |
| `Date mutation` | `date_mutation` | Format JJ/MM/AAAA (pas ISO) |
| `Nature mutation` | `nature_mutation` | |
| `Valeur fonciere` | `valeur_fonciere` | Séparateur décimal = **virgule** |
| `No voie` | `adresse_numero` | |
| `B/T/Q` | *(absent)* | Bis/Ter/Quater |
| `Type de voie` | *(absent)* | |
| `Code voie` | `adresse_code_voie` | |
| `Voie` | `adresse_nom_voie` | |
| `Code postal` | `code_postal` | |
| `Commune` | `nom_commune` | |
| `Code departement` | `code_departement` | |
| `Code commune` | `code_commune` | **3 chars** (sans préfixe département) |
| `Prefixe de section` | *(absent)* | |
| `Section` | *(absent)* | |
| `No plan` | *(absent)* | |
| `No Volume` | `numero_volume` | |
| `1er lot` à `5eme lot` | `lot1_numero` à `lot5_numero` | |
| `Surface Carrez du 1er lot` à `5eme lot` | `lot1_surface_carrez` à `lot5_surface_carrez` | |
| `Nombre de lots` | `nombre_lots` | |
| `Code type local` | `code_type_local` | |
| `Type local` | `type_local` | |
| `Identifiant local` | *(absent)* | |
| `Surface reelle bati` | `surface_reelle_bati` | |
| `Nombre pieces principales` | `nombre_pieces_principales` | |
| `Nature culture` | `nature_culture` | |
| `Nature culture speciale` | `nature_culture_speciale` | |
| `Surface terrain` | `surface_terrain` | |

> **Important** : le DVF brut n'a **pas** `id_mutation`, `longitude`, `latitude` (ajoutés par Geo-DVF). Le `Code commune` est sur **3 chars** (il faut concaténer `Code departement` + `Code commune` pour obtenir le code INSEE 5 chars).

### DPE — Diagnostic de Performance Énergétique · `P0` `✅`

- **Source** : ADEME — **Lien** : https://www.data.gouv.fr/datasets/dpe-logements-existants-depuis-juillet-2021
- **Ancien DPE** (avant juillet 2021) : https://www.data.gouv.fr/en/datasets/dpe-avant-juillet-2021/
- **Contenu** : classes énergétiques (A-G), consommation, émissions GES, caractéristiques du bâti
- **Volume** : ~9M lignes — **Format** : CSV — **MAJ** : continue (~35K nouvelles entrées/semaine)
- **Granularité** : logement individuel (agrégeable par commune)
- **Limite** : ne couvre pas tout le parc (DPE obligatoire uniquement pour vente, location ou construction neuve)
- **Tâche** : P1-3, P2-2

#### Colonnes (vérifiées sur `dpe03existant.csv` — export ADEME)

> Le dataset contient **~200 colonnes**. Voici les principales, regroupées par catégorie.
> **Attention** : certains noms de colonnes contiennent des **espaces** au lieu d'underscores (bug du dataset).

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| **Identifiants & dates** | | |
| `numero_dpe` | Identifiant unique du DPE | Non |
| `date_etablissement_dpe` | Date du diagnostic | Oui (→ `date_diagnostic`) |
| `date_fin_validite_dpe` | Date d'expiration | Non |
| `date_reception_dpe` | Date de réception | Non |
| `modele_dpe` | Modèle utilisé ("DPE 3CL 2021 méthode logement") | Non |
| `version_dpe` | Version (ex: 2.2) | Non |
| **Localisation** | | |
| `code_insee_ban` | Code INSEE (5 chars) — **attention : pas `code_commune`** | Oui (→ `code_commune`) |
| `code_postal_ban` | Code postal | Non |
| `code_departement_ban` | Code département | Non |
| `code_region_ban` | Code région | Non |
| `nom_commune_ban` | Nom de la commune | Non |
| `coordonnee_cartographique_x_ban` | Coordonnée X | Non |
| `coordonnee_cartographique_y_ban` | Coordonnée Y | Non |
| **Caractéristiques du logement** | | |
| `type_batiment` | "appartement" ou "maison" | Non (utile pour croiser avec DVF) |
| `surface_habitable_logement` | Surface en m² | Non |
| `annee_construction` | Année de construction | Non |
| `periode_construction` | Période ("2001-2005", etc.) | Non |
| `nombre_niveau_logement` | Nombre de niveaux | Non |
| `typologie_logement` | Typologie | Non |
| **Performance énergétique** | | |
| `etiquette_dpe` | Classe énergie A-G — **attention : pas `classe_dpe_energie`** | Oui (→ `classe_energie`) |
| `etiquette_ges` | Classe GES A-G | Non |
| `conso_5 usages_par_m2_ef` | Consommation énergie finale kWh/m²/an — **espace dans le nom !** | Oui (→ `consommation_moyenne`) |
| `conso_5_usages_ep` | Consommation énergie primaire totale | Non |
| `conso_5_usages_par_m2_ep` | Consommation EP par m² | Non |
| `conso_chauffage_ef` | Consommation chauffage EF | Non |
| `conso_ecs_ef` | Consommation ECS EF | Non |
| `conso_refroidissement_ef` | Consommation climatisation | Non |
| `conso_eclairage_ef` | Consommation éclairage | Non |
| `conso_auxiliaires_ef` | Consommation auxiliaires | Non |
| **Émissions GES** | | |
| `emission_ges_5_usages` | Émissions totales kg CO2 | Non |
| `emission_ges_5_usages par_m2` | Émissions GES kg CO2/m²/an — **espace dans le nom !** | Non |
| **Isolation** | | |
| `qualite_isolation_enveloppe` | Qualité globale isolation | Non |
| `qualite_isolation_murs` | Insuffisante/moyenne/bonne/très bonne | Non |
| `qualite_isolation_plancher_haut_*` | Isolation plafonds (plusieurs variantes) | Non |
| `qualite_isolation_plancher bas` | Isolation plancher — **espace dans le nom !** | Non |
| `qualite_isolation_menuiseries` | Isolation fenêtres | Non |
| **Chauffage & ECS** | | |
| `type_energie_principale_chauffage` | "Électricité", "Gaz naturel", "Fioul", "Bois"... | Non |
| `type_generateur_chauffage_principal` | Type de générateur | Non |
| `type_installation_chauffage` | "individuel" ou "collectif" | Non |
| **Énergies renouvelables** | | |
| `categorie_enr` | Catégorie ENR | Non |
| `presence_production_pv` | Présence panneaux PV | Non |

> **Mapping colonnes source → Homepedia** :
> - `etiquette_dpe` → `classe_energie` (anciennement `classe_dpe_energie`)
> - `conso_5 usages_par_m2_ef` → `consommation_moyenne` (attention à l'espace !)
> - `date_etablissement_dpe` → `date_diagnostic`
> - `code_insee_ban` → `code_commune` (anciennement `code_commune`)

#### Ancien DPE (avant juillet 2021) · `✅`

- **Source** : ADEME — **Lien** : https://www.data.gouv.fr/datasets/dpe-logements-avant-juillet-2021
- **Téléchargement** : https://object.files.data.gouv.fr/data-pipeline-open/ademe/dpe_logement_202103.sql
- **Volume** : **10 728 950 enregistrements**
- **Format** : **dump MySQL** (pas CSV) — table principale `td001_dpe`
- **Période** : avant juillet 2021 (ancienne méthode de calcul DPE)

> **Attention** : format très différent du nouveau DPE — c'est un dump SQL MySQL avec des FK vers des tables de référence (type bâtiment, département, etc.), pas un CSV plat.

##### Colonnes principales (vérifiées sur `dpe_logement_202103.sql`)

| Colonne source (ancien) | Équivalent nouveau DPE | Utilisée dans Homepedia |
|--------------------------|----------------------|------------------------|
| **Identifiants & dates** | | |
| `id` | *(absent)* | Non |
| `numero_dpe` | `numero_dpe` | Non |
| `date_etablissement_dpe` | `date_etablissement_dpe` | Oui (→ `date_diagnostic`) |
| `date_visite_diagnostiqueur` | *(absent)* | Non |
| `date_reception_dpe` | `date_reception_dpe` | Non |
| `nom_methode_dpe` | `modele_dpe` | Non |
| `version_methode_dpe` | `version_dpe` | Non |
| **Localisation** | | |
| `code_insee_commune` | `code_insee_ban` | Oui (→ `code_commune`) |
| `code_insee_commune_actualise` | *(absent)* | Non (utile pour fusions) |
| `code_postal` | `code_postal_ban` | Non |
| `commune` | `nom_commune_ban` | Non |
| `tv016_departement_id` | `code_departement_ban` | Non (**FK**, pas le code directement) |
| `type_voie`, `nom_rue`, `numero_rue` | *(absent)* | Non |
| `arrondissement` | *(absent)* | Non |
| **Performance énergétique** | | |
| `classe_consommation_energie` | `etiquette_dpe` | Oui (→ `classe_energie`, varchar(1) A-G) |
| `consommation_energie` | `conso_5 usages_par_m2_ef` | Oui (→ `consommation_moyenne`, decimal) |
| `classe_estimation_ges` | `etiquette_ges` | Non (varchar(1) A-G) |
| `estimation_ges` | `emission_ges_5_usages par_m2` | Non |
| **Caractéristiques du logement** | | |
| `tr002_type_batiment_id` | `type_batiment` | Non (**FK** → table `tr002_type_batiment`, pas texte direct) |
| `annee_construction` | `annee_construction` | Non |
| `surface_habitable` | `surface_habitable_logement` | Non |
| `nombre_niveaux` | `nombre_niveau_logement` | Non |
| **Autres** | | |
| `dpe_vierge` | *(absent)* | Non (filtrer : DPE vierges = sans consommation réelle) |
| `est_efface` | *(absent)* | Non (filtrer : DPE annulés) |
| `organisme_certificateur` | *(absent)* | Non |

> **Mapping ancien DPE → Homepedia** :
> - `classe_consommation_energie` → `classe_energie` (même valeur A-G que le nouveau)
> - `consommation_energie` → `consommation_moyenne` (decimal, pas d'espace dans le nom)
> - `code_insee_commune` → `code_commune` (même format 5 chars)
> - `date_etablissement_dpe` → `date_diagnostic` (identique au nouveau)
>
> **Pièges** :
> - `tr002_type_batiment_id` est une **FK** (int) → il faut joindre avec `tr002_type_batiment` pour avoir "maison"/"appartement"
> - `tv016_departement_id` est une **FK** (int) → il faut joindre avec `tv016_departement` pour avoir le code département
> - Filtrer `dpe_vierge = 0` ET `est_efface = 0` pour exclure les DPE vierges/annulés
> - Le dump est en **MySQL** — il faudra le convertir ou l'importer via MySQL puis exporter en CSV/Parquet pour PySpark

### Carte des loyers par commune · `P0` `✅`

- **Source** : MEF / DHUP (Ministère de l'Économie et des Finances)
- **Lien** : https://www.data.gouv.fr/datasets/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025
- **Contenu** : Loyer prédit au m² par commune, avec intervalle de confiance
- **Granularité** : Commune — **Format** : CSV (séparateur `;`) — **MAJ** : Annuelle
- **Intérêt** : rendement locatif = critère #1 des investisseurs

#### Fichiers (vérifiés)

| Fichier | Contenu |
|---------|---------|
| `pred-app-mef-dhup.csv` | Appartements (tous) |
| `pred-mai-mef-dhup.csv` | Maisons |
| `pred-app3-mef-dhup.csv` | Appartements 3+ pièces |
| `pred-app12-mef-dhup.csv` | Appartements 1-2 pièces |

> Les 4 fichiers ont la **même structure** (~35K lignes chacun).

#### Colonnes (vérifiées)

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `INSEE_C` | Code commune INSEE (5 chars) | Oui (→ `code_commune`) |
| `LIBGEO` | Nom commune | Non |
| `EPCI` | Code EPCI | Non |
| `DEP` | Code département | Non |
| `REG` | Code région | Non |
| `loypredm2` | **Loyer prédit au m² (€/m²)** | Oui |
| `lwr.IPm2` | Borne basse intervalle de prédiction | Non |
| `upr.IPm2` | Borne haute intervalle de prédiction | Non |
| `TYPPRED` | Type de prédiction ("commune" ou "maille") | Non |
| `nbobs_com` | Nb observations dans la commune | Non |
| `nbobs_mail` | Nb observations dans la maille | Non |
| `R2_adj` | R² ajusté du modèle | Non |

### LOVAC — Logements vacants du parc privé · `P1` `✅`

- **Source** : DGFiP (fichier 1767Biscom + Fichiers Fonciers)
- **Lien** : https://www.data.gouv.fr/datasets/logements-vacants-du-parc-prive-par-commune-departement-region
- **Contenu** : Nombre de logements privés vacants, dont vacants > 2 ans (longue durée)
- **Granularité** : Commune — **Format** : CSV (séparateur `;`) — **Période** : 2020-2025
- **Intérêt** : indicateur de tension/dévitalisation du marché

#### Colonnes (vérifiées sur `lovac-opendata-communes.csv`)

> Fichier en format **semi-long** : une ligne par commune, colonnes par millésime (2020-2025). ~35K lignes.

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `CODGEO_25` | Code commune INSEE (5 chars) | Oui (→ `code_commune`) |
| `LIBGEO_25` | Nom commune | Non |
| `pp_vacant_25` | Nb logements privés vacants (2025) | Oui |
| `pp_vacant_plus_2ans_25` | Nb vacants > 2 ans (2025, longue durée) | Oui |
| `pp_total_24` | Nb total logements privés (2024) | Oui (calcul taux vacance) |
| `pp_vacant_24` / `pp_vacant_plus_2ans_24` | Idem pour 2024 | Oui (historique) |
| `pp_total_23` à `pp_vacant_20` | Séries 2020-2023 | Oui (historique) |
| `EPCI_25` / `LIB_EPCI_25` | Code et nom EPCI | Non |
| `DEP` / `LIB_DEP` | Code et nom département | Non |
| `REG` / `LIB_REG` | Code et nom région | Non |

> **Note** : le fichier Excel `lovac-open-data-2020-a-2025-vd.xlsx` contient les mêmes données avec des sheets FR/REG/DEP/COM + métadonnées.
> Le taux de vacance se calcule : `pp_vacant / pp_total * 100`.

### Zonage ABC (tension immobilière) · `P1` `✅`

- **Source** : MEF / DHUP
- **Lien** : https://www.data.gouv.fr/datasets/liste-des-communes-par-zone-du-dispositif-pinel
- **Contenu** : Classification des communes en zones A, Abis, B1, B2, C selon la tension du marché immobilier
- **Granularité** : Commune — **Format** : CSV (séparateur `;`) — **MAJ** : Ponctuelle (dernière : 5 sept. 2025)
- **Intérêt** : éligibilité Pinel/PTZ, impact direct sur l'attractivité immobilière

#### Colonnes (vérifiées sur `liste-des-communes-zonage-abc-5-septembre-2025.csv`)

> ~35K lignes (une par commune).

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `CODGEO` | Code commune INSEE (5 chars) | Oui (→ `code_commune`) |
| `DEP` | Code département | Non |
| `LIBGEO` | Nom commune | Non |
| `Zonage en vigueur depuis le 5 septembre 2025` | Zone : A, Abis, B1, B2 ou C | Oui (→ `zone_abc`) |
| `Reclassement 5 septembre 2025` | "Oui" ou "Non" (reclassé récemment) | Non |

### RPLS — Logements locatifs sociaux · `P2` `✅`

- **Source** : SDES (Ministère de la Transition Écologique)
- **Lien** : https://www.data.gouv.fr/datasets/donnees-detaillees-au-logement-du-repertoire-des-logements-locatifs-des-bailleurs-sociaux-rpls
- **Contenu** : Parc social détaillé au logement : type, financement, surface, DPE, géolocalisation
- **Granularité** : **logement individuel** (géolocalisé — cliquable sur la carte)
- **Format** : CSV (séparateur `;`) — **MAJ** : annuelle (au 1er janvier)

#### Colonnes (vérifiées sur `Donnees-detaillees-au-logement-du-repertoire-des-logements-locatifs-des-bailleurs-sociau.2025-01.csv`)

> Le fichier contient **73 colonnes**. Voici les principales, regroupées par catégorie.

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| **Localisation** | | |
| `Code Commune` | Code commune INSEE (5 chars) | Oui (→ `code_commune`) |
| `Code Postal` | Code postal | Non |
| `Libéllé Commune` | Nom commune (typo "Libéllé" dans le fichier) | Non |
| `Région - Code de la zone` | Code région | Non |
| `Département - Code de la zone` | Code département | Non |
| `EPCI - Code de la zone` | Code EPCI | Non |
| `Numéro de voie`, `Type de voie`, `Nom de voie` | Adresse | Non |
| `Coordonnée X`, `Coordonnée Y` | Géolocalisation (système indiqué dans `Système de coordonnées utilisée`) | Oui (affichage bâtiment sur carte) |
| `Code IRIS - Code de la zone` | Code IRIS | Non |
| **Caractéristiques du logement** | | |
| `Type de construction - Libellé` | Type de construction | Non |
| `Nombre de pièces` | Nombre de pièces | Non |
| `Surface habitable` | Surface en m² | Oui (stats) |
| `Etage` | Étage du logement | Non |
| `Année de construction` | Année de construction | Non |
| `Année de première mise en location` | Première mise en location | Non |
| **Financement & convention** | | |
| `Droit - Libellé` | Type de droit (pleine propriété, etc.) | Non |
| `Financement initial - Libellé` | PLUS, PLAI, PLS, etc. | Oui (répartition par type) |
| `Convention APL` | Convention APL oui/non | Non |
| `Alinéa SRU` | Comptabilisation SRU | Non |
| `Catégorie financement CUS` | Catégorie CUS | Non |
| **Performance énergétique** | | |
| `Etiquette DPE Energie` | Classe énergie A-G | Non (croisement avec DPE possible) |
| `Etiquette DPE GES` | Classe GES A-G | Non |
| `Date du DPE` | Date du diagnostic | Non |
| **Quartiers prioritaires** | | |
| `Situation en QPV - Code` | Code QPV | Non |
| `Code QPV 2024`, `Code QPV 2015` | Codes QPV multi-millésimes | Non |
| `Indicatrice de présence d'un QPV dans la commune` | QPV dans la commune oui/non | Non |
| **Accessibilité** | | |
| `Accessibilité PMR - Libellé` | Accessibilité PMR | Non |

> **Note** : le fichier contient **une ligne par logement social**. Pour obtenir des statistiques communales (nombre de logements sociaux, répartition par financement, surface moyenne), il faut agréger par `Code Commune`.
> Les coordonnées X/Y permettent l'**affichage individuel sur la carte** (clic sur un bâtiment).

### Sources immobilières exclues

#### ~~Nombre de ventes (maisons et appartements anciens)~~ · `EXCLU`

> **Raison** : granularité France entière uniquement — pas de ventilation par commune ou département. Le DVF fournit déjà les volumes de transactions par commune.

#### ~~Permis d'aménager (Sitadel)~~ · `EXCLU`

> **Raison** : volume trop faible (~2 100 lignes). Ne contient que les permis d'**aménager** (PA), pas les permis de construire (PC). Inutilisable pour des analyses communales.

---

## 2. Données socio-économiques

### FiLoSoFi — Revenus localisés sociaux et fiscaux · `P0` `✅`

- **Source** : INSEE / DGFiP — **Lien** : https://www.data.gouv.fr/fr/datasets/revenus-localises-sociaux-et-fiscaux-dispositif-filosofi/
- **Contenu** : revenu médian, taux de pauvreté, distribution des revenus, niveau de vie
- **Format** : CSV — **Granularité** : commune, IRIS, carreaux
- **Intérêt** : corrélation prix immobilier / pouvoir d'achat local
- **Tâche** : P1-5

#### Colonnes (vérifiées sur `BASE_TD_FILO_DEC_IRIS_2018.xlsx`)

> **Attention** : le fichier téléchargé est au niveau **IRIS** (pas communal). Les colonnes sont en **clair** (pas codées `MED{YY}`).
> Les 5 premières lignes sont des en-têtes descriptifs — les données commencent à la ligne 6.

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `IRIS` | Code IRIS | Non (agrégé au niveau commune) |
| `Libellé de l'IRIS` | Nom de l'IRIS | Non |
| `Commune ou ARM` | Code commune ou arrondissement | Oui (→ `code_commune`) |
| `Libellé commune ou ARM` | Nom de la commune | Non |
| `Part des ménages fiscaux imposés (%)` | % ménages imposés | Non |
| `Taux de bas revenus déclarés au seuil de 60 % (%)` | Taux de pauvreté | Oui (→ `taux_pauvrete`) |
| `1er quartile (€)` | Q1 revenus | Non |
| `Médiane (€)` | Revenu médian | Oui (→ `revenu_median`) |
| `3e quartile (€)` | Q3 revenus | Non |
| `Écart inter-quartile rapporté à la médiane` | Dispersion | Non |
| `1er décile (€)` à `9e décile (€)` | Déciles D1-D9 | Non |
| `Rapport interdécile D9/D1` | Ratio interdécile | Non |
| `S80/S20` | Ratio masses S80/S20 | Non |
| `Indice de Gini` | Indice d'inégalité | Non |
| `Part des revenus d'activité (%)` | % revenus activité | Non |
| `dont part des salaires et traitements (%)` | % salaires | Non |
| `dont part des indemnités de chômage (%)` | % chômage | Non |
| `dont part des revenus des activités non salariées (%)` | % non-salariés | Non |
| `Part des pensions, retraites et rentes (%)` | % pensions | Non |
| `Part des autres revenus (%)` | % autres | Non |

> **Mapping** : `Commune ou ARM` → `code_commune`, `Médiane (€)` → `revenu_median`, `Taux de bas revenus déclarés au seuil de 60 % (%)` → `taux_pauvrete`.
> Le fichier `BASE_TD_FILO_DISP_IRIS_2018.xlsx` contient les revenus **disponibles** (après impôts/prestations) — même structure, colonnes différentes.

### Impôts locaux (REI) · `P1` `✅`

- **Source** : DGFiP
- **Lien** : https://www.data.gouv.fr/datasets/impots-locaux-fichier-de-recensement-des-elements-dimposition-a-la-fiscalite-directe-locale-rei-4
- **Volume** : **34 940 lignes** (une par commune) × **1101 colonnes** — **Format** : CSV (séparateur `;`, encodage Latin-1)
- **Période** : 2024 (un ZIP par année disponible depuis 1982)
- **Granularité** : Commune
- **Intérêt** : taxe foncière = coût de possession d'un bien
- **Téléchargement** : ZIP annuel (`REI-2024-fichier-notice-trace.zip`), contient CSV + notice PDF + trace XLSX

> **Attention** : le CSV direct sur data.gouv.fr est vide (métadonnées uniquement). Il faut télécharger le **ZIP par année**.

#### Colonnes principales (vérifiées sur `REI_2024.csv`)

> **1101 colonnes** avec des codes cryptiques (B11, E12, H13...). La notice `Notice_explicative_REI_2024.pdf` détaille chaque code.
> Seules les colonnes pertinentes pour Homepedia sont listées ci-dessous.

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `IDCOM` | Code commune INSEE (5 chars) — **colonne 1101** | Oui (→ `code_commune`) |
| `DEP` | Code département | Non (redondant) |
| `COM` | Code commune (3 chars, sans préfixe département) | Non (utiliser `IDCOM`) |
| `LIBCOM` | Nom de la commune | Non |
| **Taxe foncière sur le bâti** | | |
| `B11` | Base nette imposable (€) | Non |
| `B12` | Taux communal (%) | Oui (→ `taux_taxe_fonciere`) |
| `B13` | Cotisation communale (€) | Non |
| `B14` | Nombre d'articles (logements imposés) | Non |
| **Taxe foncière sur le non-bâti** | | |
| `E11` | Base nette imposable (€) | Non |
| `E12` | Taux communal (%) | Non |
| **Taxe d'habitation (résidences secondaires)** | | |
| `H12` | Taux communal TH (%) | Non |
| `H14` | Nombre d'articles | Non |
| **CFE (Cotisation Foncière des Entreprises)** | | |
| `P11` | Base nette imposable (€) | Non |
| `P12` | Taux communal (%) | Non |

> **Mapping** : `IDCOM` → `code_commune`, `B12` → `taux_taxe_fonciere` (le taux communal de taxe foncière sur le bâti est l'indicateur le plus pertinent pour Homepedia).
> **Piège** : le code commune est dans `IDCOM` (dernière colonne, #1101), pas dans `DEP`+`COM`.

### Populations municipales historiques · `P0` `✅`

| | |
|---|---|
| **Source** | INSEE |
| **Lien** | https://www.insee.fr/fr/statistiques/3698339 |
| **Contenu** | Populations communales de 1876 à 2023 — évolution démographique longue |
| **Format** | Excel (.xlsx, 6 MB) — fichier unique |
| **Granularité** | Commune |
| **MAJ** | Annuelle (dernière : décembre 2025) |
| **Intérêt** | Dynamisme démographique = indicateur clé d'attractivité communale |
| **Notes** | Métropole depuis 1876, Corse depuis 1936, DOM depuis 1954/1962. Homepedia utilise 1968-2023. Paris par arrondissement, Lyon/Marseille par commune entière. |

### Comptes des communes (finances locales) · `P2` `✅`

- **Source** : Observatoire des Finances et de la Gestion publique Locales
- **Lien** : https://www.data.gouv.fr/datasets/comptes-des-communes-2017-2024
- **Volume** : **22 364 887 lignes** (6.8 GB) — **Format** : CSV (séparateur `;`, BOM UTF-8)
- **Période** : 2017-2024
- **Granularité** : Commune

#### Colonnes (vérifiées sur `ofgl-base-communes.csv`)

> Format **long** : une ligne par commune × exercice × agrégat. ~30 agrégats financiers différents.

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `Exercice` | Année (2017-2024) | Oui (filtre année) |
| `Code Insee 2024 Commune` | Code commune INSEE (5 chars) | Oui (→ `code_commune`) |
| `Nom 2024 Commune` | Nom de la commune | Non |
| `Code Insee 2024 Région` | Code région | Non |
| `Code Insee 2024 Département` | Code département | Non |
| `Strate population 2024` | Strate de population | Non |
| `Commune rurale` | Oui/Non | Non |
| `Commune de montagne` | Oui/Non | Non |
| `Commune touristique` | Oui/Non | Non |
| `Tranche revenu par habitant` | Tranche de revenu | Non |
| `Présence QPV` | Quartier prioritaire oui/non | Non |
| `Agrégat` | Type d'indicateur financier (voir liste ci-dessous) | Oui (pivot) |
| `Montant` | Montant en euros | Oui |
| `Montant en € par habitant` | Montant par habitant | Oui |
| `Population totale` | Population | Non (redondant) |
| `Type de budget` | "Budget principal" ou "Budget annexe" | Non (filtrer "Budget principal") |

#### Principaux agrégats disponibles (colonne `Agrégat`)

> Recettes fiscales, DGF, épargne brute, encours de dette, dépenses d'équipement, charges de personnel, etc. (~30 agrégats au total)

> **Note** : fichier massif (6.8 GB, 22M lignes). Filtrer `Type de budget = "Budget principal"` et pivoter par `Agrégat` lors du processing.

### Sources socio-économiques exclues

#### ~~Data INSEE sur les communes~~ · `EXCLU`

> **Raison** : dataset abandonné (dernière MAJ décembre 2014, plus maintenu). Les données qu'il couvrait (population, démographie, activité économique, emploi) sont disponibles en plus récent via FiLoSoFi, BPE, France Travail et le recensement INSEE.

---

## 3. Emploi et chômage

### Demandeurs d'emploi par commune (France Travail) · `P0` `✅`

- **Source** : DARES / France Travail
- **Lien** : https://www.data.gouv.fr/en/datasets/demandeurs-demploi-inscrits-a-france-travail-donnees-communales-trimestrielles-brutes/
- **Volume** : **2 095 020 lignes** — **Format** : CSV (séparateur `;`, BOM UTF-8)
- **Granularité** : Commune
- **Période** : 2015-T4 à 2024-T4 (**T4 uniquement** — snapshot annuel, pas les 4 trimestres)
- **Tâche** : P1-5

#### Colonnes (vérifiées sur `dares_defm_communales-brutes.csv`)

> Format **long** : une ligne par commune × sexe × tranche d'âge × trimestre.

| Colonne source | Description | Valeurs | Utilisée dans Homepedia |
|----------------|-------------|---------|------------------------|
| `Date` | Trimestre (format `YYYY-TN`) | 2015-T4 à 2024-T4 | Oui (filtre année) |
| `Code région` | Code région | ex: 44 | Non |
| `Région` | Nom de la région | ex: Grand-Est | Non |
| `Code département` | Code département | ex: 88 | Non |
| `Département` | Nom du département | ex: Vosges | Non |
| `Code commune` | Code commune INSEE (5 chars) | ex: 88083 | Oui (→ `code_commune`) |
| `Commune` | Nom de la commune | ex: Certilleux | Non |
| `Type de données` | Type | `Brutes` uniquement | Non |
| `Catégorie` | Catégorie de demandeurs | `ABC` uniquement (A+B+C combinées) | Non |
| `Sexe` | Sexe | `Total`, `Hommes`, `Femmes` | Non (filtrer `Total`) |
| `Tranche d'âge` | Tranche d'âge | `Total`, `Moins de 25 ans`, `De 25 à 49 ans`, `50 ans et plus` | Non (filtrer `Total`) |
| `Nombre de demandeurs d'emploi` | Nombre de demandeurs | entier | Oui (→ `nb_demandeurs_emploi`) |

> **Mapping** : filtrer `Sexe = "Total"` ET `Tranche d'âge = "Total"` pour obtenir un nombre par commune par année.
> **Attention** : le fichier a un **BOM UTF-8** (`﻿` devant `Date`) — à gérer au parsing.
> **Limite** : seul le T4 est disponible au niveau communal (les données trimestrielles complètes sont au niveau départemental).

### Sources emploi exclues

#### ~~Marché du travail (INSEE — BDM)~~ · `EXCLU`

> **Raison** : granularité départementale/régionale uniquement, pas communale. Redondant avec France Travail qui est communal. MAJ février 2026.

#### ~~Enquête emploi en continu~~ · `EXCLU`

> **Raison** : granularité nationale uniquement (enquête ménages), inutilisable à l'échelle communale.

#### ~~Données IRIS / commune / zone d'emploi~~ · `EXCLU`

> **Raison** : dernière MAJ 2022, données obsolètes. Redondant avec France Travail (communal) et BPE (équipements).

---

## 4. Équipements et services

### BPE — Base Permanente des Équipements · `P0` `✅`

- **Source** : INSEE — **Lien** : https://www.data.gouv.fr/datasets/base-permanente-des-equipements-1
- **Contenu** : inventaire des équipements et services (commerces, santé, enseignement, sport, loisirs, transports)
- **Volume** : ~2M lignes — **Format** : CSV — **Granularité** : commune et IRIS
- **Note** : contient aussi des équipements transport (gares, arrêts de bus) — **alternative au GTFS**, plus simple à intégrer
- **Tâche** : P1-4, P2-3

#### Colonnes (vérifiées sur `BPE24.csv` — séparateur `;`)

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `AN` | Année de référence | Non |
| `NOMRS` | Nom de la raison sociale | Non |
| `CNOMRS` | Complément nom | Non |
| `NUMVOIE` | Numéro de voie | Non |
| `INDREP` | Indice de répétition | Non |
| `TYPVOIE` | Type de voie | Non |
| `LIBVOIE` | Libellé voie | Non |
| `CADR` | Cadrage | Non |
| `CODPOS` | Code postal | Non |
| `DEPCOM` | Code commune INSEE (5 chars) — **attention : pas `code_commune`** | Oui (→ `code_commune`) |
| `DEP` | Code département | Non |
| `REG` | Code région | Non |
| `LIBCOM` | Libellé commune | Non |
| `DOM` | Domaine d'activité (A=enseignement, B=commerce, D=santé, E=transport...) | Non |
| `SDOM` | Sous-domaine | Non |
| `TYPEQU` | Code type d'équipement (ex: "A101" = école maternelle, "D201" = médecin) | Oui |
| `SIRET` | Numéro SIRET | Non |
| `STATUT_DIFFUSION` | Statut de diffusion | Non |
| `CANTINE`, `INTERNAT`, `RPI`, `EP`, `CL_PGE`, `SECT` | Attributs spécifiques enseignement | Non |
| `ACCES_*`, `PRES_*`, `COUVERT`, `ECLAIRE` | Attributs spécifiques sport | Non |
| `CATEGORIE`, `MULTIPLEXE` | Attributs cinéma | Non |
| `STRUCTURE_EXERCICE`, `SPECIALITE` | Attributs santé | Non |
| `LAMBERT_X`, `LAMBERT_Y` | Coordonnées Lambert 93 | Non |
| `LONGITUDE`, `LATITUDE` | Coordonnées WGS-84 | Non |

> **Note** : le fichier contient **une ligne par équipement** (pas de colonne `NB_EQUIP`). Il faut compter (`COUNT`) les lignes par `DEPCOM` + `TYPEQU` lors du processing.

> **229 types d'équipements** (`TYPEQU`), organisés en gammes (proximité, intermédiaire, supérieure).
> Homepedia agrège ces 229 types en 9 catégories dans le processing :

| Catégorie Homepedia | Codes TYPEQU source (exemples) |
|---------------------|-------------------------------|
| `nb_ecoles` | A101 (maternelle), A104 (élémentaire) |
| `nb_colleges` | A201 |
| `nb_lycees` | A301-A305 |
| `nb_medecins` | D201 (généraliste) |
| `nb_dentistes` | D202 |
| `nb_pharmacies` | D301 |
| `nb_hopitaux` | D101-D108 |
| `nb_gares` | E101-E107 |
| `nb_supermarches` | B101-B304 |

> **À vérifier** : les codes TYPEQU exacts lors du téléchargement du dataset. Le fichier `BPE24_liste_hierarchisee_TYPEQU.html` sur insee.fr contient la liste complète.

---

## 5. Éducation

### Résultats du Brevet (DNB) par établissement · `P1` `✅`

- **Source** : Ministère de l'Éducation Nationale
- **Lien** : https://www.data.gouv.fr/datasets/diplome-national-du-brevet-par-etablissement-1
- **Contenu** : Taux de réussite, mentions, par collège
- **Format** : CSV (séparateur `;`)
- **Tâche** : P1-7

#### Colonnes (vérifiées sur `fr-en-dnb-par-etablissement.csv`)

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `Session` | Année de la session (ex: 2012) | Oui (filtre année) |
| `Numero d'etablissement` | Code UAI de l'établissement | Non |
| `Type d'etablissement` | "COLLEGE" | Non |
| `Patronyme` | Nom de l'établissement | Non |
| `Secteur d'enseignement` | "PUBLIC" ou "PRIVE" | Non |
| `Commune` | Code commune INSEE (5 chars) | Oui (→ `code_commune`) |
| `Libellé commune` | Nom de la commune | Non |
| `Code département` | Code département | Non |
| `Libellé département` | Nom du département | Non |
| `Code académie` | Code académie | Non |
| `Code région` | Code région | Non |
| `Inscrits` | Nombre d'inscrits | Non |
| `Presents` | Nombre de présents | Oui |
| `Admis` | Nombre total d'admis | Oui |
| `Admis sans mention` | Sans mention | Non |
| `Nombre_d_admis_Mention_AB` | Mention Assez Bien | Non |
| `Admis Mention bien` | Mention Bien | Non |
| `Admis Mention très bien` | Mention Très Bien | Non |
| `Taux de réussite` | % de réussite (format "93,20%") | Oui |

### Indicateurs de valeur ajoutée des lycées (IVAL) · `P1` `✅`

- **Source** : Ministère de l'Éducation Nationale
- **Lien** : https://www.data.gouv.fr/datasets/indicateurs-de-valeur-ajoutee-des-lycees-denseignement-general-et-technologique-ancien
- **Contenu** : Taux de réussite au bac, taux d'accès, valeur ajoutée par lycée
- **Format** : CSV (séparateur `;`)
- **Tâche** : P1-7

#### Colonnes (vérifiées sur `fr-en-indicateurs-de-resultat-des-lycees-...csv`)

> Le fichier contient des colonnes par série (L, ES, S, STG, STI2D, STD2A, STMG, STI, STL, ST2S, TMD, STHR, Toutes series).

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `Etablissement` | Nom du lycée | Non |
| `Annee` | Année | Oui |
| `Ville` | Nom de la ville | Non |
| `UAI` | Code UAI de l'établissement | Non |
| `Code commune` | Code commune INSEE (5 chars) | Oui (→ `code_commune`) |
| `Academie` | Nom de l'académie | Non |
| `Departement` | Nom du département | Non |
| `Secteur` | "public" ou "privé" | Non |
| `Presents - Toutes series` | Nb total de candidats | Oui |
| `Taux de reussite - Toutes series` | Taux de réussite global (%) | Oui |
| `Taux de reussite attendu acad - Toutes series` | Taux attendu académie | Non |
| *(colonnes par série L, ES, S, etc.)* | Présents + taux par série | Non |

> **Note** : les colonnes `Code commune` (DNB) et `Code commune` (IVAL) utilisent le code INSEE 5 chars directement.

---

## 6. Sécurité

### Bases statistiques de la délinquance · `P1` `✅`

- **Source** : SSMSI (Ministère de l'Intérieur)
- **Lien** : https://www.data.gouv.fr/datasets/bases-statistiques-communale-departementale-et-regionale-de-la-delinquance-enregistree-par-la-police-et-la-gendarmerie-nationales
- **Contenu** : principaux indicateurs de crimes et délits enregistrés par police et gendarmerie
- **Période** : depuis 2016 — **Format** : CSV — **Granularité** : commune, département, région
- **Seuil de diffusion** : communes avec >5 faits sur 3 ans consécutifs
- **Tâche** : P1-6

#### Colonnes et format (vérifié sur `donnee-comm-data.gouv-parquet-2024-geographie2025`)

> **Important** : le fichier est en format **long** (une ligne par indicateur par commune par année), PAS en format large.
> **4 714 200 lignes** au total.

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `CODGEO_2025` | Code commune INSEE (5 chars) — **attention : pas `CODGEO` ni `code_commune`** | Oui (→ `code_commune`) |
| `annee` | Année (depuis 2016) | Oui |
| `indicateur` | Catégorie d'infraction (texte, voir ci-dessous) | Oui (→ pivot en colonnes) |
| `unite_de_compte` | "Victime" ou "Mis en cause" selon l'indicateur | Oui (filtrer sur le bon type) |
| `nombre` | Nombre de faits constatés | Oui (→ valeur pivotée) |
| `taux_pour_mille` | Taux pour 1 000 habitants (pré-calculé) | Oui |
| `est_diffuse` | `"diff"` ou `"ndiff"` (seuil de diffusion) | Oui (filtrer `diff` uniquement) |
| `insee_pop` | Population INSEE de la commune | Oui (→ `population`) |
| `insee_pop_millesime` | Année du millésime population | Non |
| `insee_log` | Nombre de logements INSEE | Non |
| `insee_log_millesime` | Année du millésime logements | Non |
| `complement_info_nombre` | Info complémentaire sur le nombre | Non |
| `complement_info_taux` | Info complémentaire sur le taux | Non |

#### Les 15 indicateurs d'infractions (valeurs réelles dans la colonne `indicateur`)

| # | Indicateur | Unité de compte |
|---|------------|-----------------|
| 1 | Violences physiques intrafamiliales | Victime |
| 2 | Violences physiques hors cadre familial | Victime |
| 3 | Violences sexuelles | Victime |
| 4 | Vols avec armes | Victime |
| 5 | Vols violents sans arme | Victime |
| 6 | Vols sans violence contre des personnes | Victime |
| 7 | Cambriolages de logement | Logement |
| 8 | Vols de véhicule | Véhicule |
| 9 | Vols dans les véhicules | Véhicule |
| 10 | Vols d'accessoires sur véhicules | Véhicule |
| 11 | Destructions et dégradations volontaires | Victime |
| 12 | Escroqueries et fraudes aux moyens de paiement | Victime |
| 13 | Trafic de stupéfiants | Mis en cause |
| 14 | Usage de stupéfiants | Mis en cause |
| 15 | Usage de stupéfiants (AFD) | Mis en cause |

> **Note** : les communes avec `est_diffuse = "ndiff"` ont `nombre = NaN` (seuil de diffusion < 5 faits sur 3 ans). Les valeurs approximatives sont dans `complement_info_nombre`.

---

## 7. Transports

> **Décision** : la BPE (section 4) contient déjà les gares et arrêts de bus par commune (`TYPEQU` E101-E107). Le GTFS est trop complexe (format multi-fichiers) pour un gain marginal. On utilise la BPE comme source transport principale.

### Déplacements domicile-travail · `P2` `✅`

| | |
|---|---|
| **Source** | INSEE |
| **Lien** | https://www.data.gouv.fr/fr/datasets/deplacements-domicile-travail/ |
| **Contenu** | Population 15+ ayant un emploi selon lieu de travail + mode de transport utilisé |
| **Volume** | ~70 MB (CSV dans ZIP ~12 MB) — 1.19M lignes dont 972K au niveau commune |
| **Granularité** | Multi-niveaux (commune, EPCI, département, région, zone emploi, AAV, France) |
| **Période** | 2022 |
| **MAJ** | Septembre 2025 |
| **Intérêt** | Attractivité économique, dépendance à la voiture |
| **Priorité basse** | La BPE (§4) couvre déjà gares et arrêts de bus par commune (`TYPEQU` E101-E107) |

#### Colonnes (vérifiées sur `DS_RP_NAVETTES_PRINC_2022_data.csv`)

> **Format long** (une observation par ligne), pas un format tabulaire classique.

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `GEO` | Code géographique (code commune, EPCI, etc.) | Oui (filtrer `GEO_OBJECT=COM` → `code_commune`) |
| `GEO_OBJECT` | Type géo (`COM`, `DEP`, `REG`, `EPCI`, `ARM`...) | Oui (filtre) |
| `TRANS` | Mode transport (`1`=pas de transport, `2`=marche, `3`=vélo, `4`=2 roues, `5`=voiture, `6`=transport en commun, `_T`=total) | Oui |
| `WORK_AREA` | Zone de travail | Oui |
| `OBS_VALUE` | Valeur (population) | Oui |
| `AGE` | Tranche d'âge (`Y_GE15`) | Non (filtre) |
| `EMPSTA_ENQ` | Statut emploi (`1`=actif occupé) | Non (filtre) |
| `TIME_PERIOD` | Année (2022) | Non |

### Sources transport exclues

#### ~~GTFS (transport.data.gouv.fr)~~ · `EXCLU`

> **Raison** : format complexe (multi-fichiers liés), couverture incomplète (communes rurales absentes). La BPE couvre déjà les gares et arrêts par commune, suffisant pour Homepedia.

---

## 8. Santé

> **Décision** : la BPE couvre déjà les établissements de santé par commune (hôpitaux D101-D108, médecins D201, pharmacies D301). On ajoute uniquement la **densité médicale** pour l'indicateur "déserts médicaux".

### Densité médicale par commune · `P1` `⬜`

| | |
|---|---|
| **Lien** | https://www.data.gouv.fr/en/datasets/sante-densite-medecins/ |
| **Contenu** | Densité de médecins au niveau communal |
| **Granularité** | Commune |
| **Format** | CSV |
| **Intérêt** | Identifier les déserts médicaux — critère de qualité de vie |

### Sources santé exclues

#### ~~Démographie des médecins (RPPS)~~ · `EXCLU`

> **Raison** : redondant avec BPE (comptage médecins par commune) + densité médicale (indicateur pré-calculé).

#### ~~Démographie des professionnels de santé (2012-2024)~~ · `EXCLU`

> **Raison** : granularité départementale, pas communale.

#### ~~Professionnels de santé libéraux~~ · `EXCLU`

> **Raison** : granularité départementale/régionale, pas communale.

---

## 9. Élections · `P2`

> **Décision** : seule la **nuance politique du maire** est pertinente pour Homepedia (une donnée par commune, exploitable en choropleth). Les résultats détaillés par scrutin sont hors périmètre.

### Communes enrichies avec nuance politique · `P2` `⬜`

| | |
|---|---|
| **Source** | Datactivist |
| **Lien** | https://www.data.gouv.fr/datasets/communes-enrichies-avec-la-nuance-politique-france |
| **Contenu** | Nuance politique du maire par commune (basée sur les municipales 2020) : nom commune, code INSEE, SIREN, nuance, famille politique |
| **Format** | CSV (UTF-8) |
| **Intérêt** | Carte politique par commune |

### Sources élections exclues

#### ~~Données électorales détaillées, répertoire des élus~~ · `EXCLU`

> **Raison** : trop granulaire (bureau de vote), pas de lien direct avec l'immobilier. La nuance politique suffit.

---

## 10. Risques naturels et environnement

### API Géorisques · `P1` `⬜`

| | |
|---|---|
| **Source** | BRGM / Ministère de la Transition Écologique |
| **Lien** | https://www.data.gouv.fr/dataservices/api-georisques |
| **Contenu** | API qui retourne pour un territoire la liste des risques naturels et technologiques : inondation, séisme, mouvement de terrain, retrait-gonflement argiles, radon, installations classées (ICPE) |
| **Granularité** | Adresse, parcelle, commune |
| **Format** | API REST (JSON) |
| **Intérêt** | L'ERRIAL (État des Risques) est obligatoire pour toute vente/location — très pertinent immobilier |

### Sources risques exclues

#### ~~Zones inondables (TRI)~~ · `EXCLU`

> **Raison** : format SHP/GeoJSON complexe, ne couvre que 124 territoires. Géorisques agrège déjà ces données.

#### ~~PPRN (Plans de Prévention)~~ · `EXCLU`

> **Raison** : redondant avec API Géorisques qui inclut les PPRI.

#### ~~Cartes du bruit / PEB aéroports~~ · `EXCLU`

> **Raison** : format SHP complexe, couverture partielle (grandes agglomérations et aéroports uniquement). Intégration coûteuse pour un gain marginal.

---

## 11. Météo et climat

> **Décision** : on ne veut pas les données brutes quotidiennes (trop lourdes — 626 fichiers .gz, jointure spatiale complexe). L'indicateur utile pour Homepedia est simple : **ensoleillement annuel** par département.

### Ensoleillement par département · `P1` `✅`

| | |
|---|---|
| **Source** | Hello Watt (données Météo-France agrégées) |
| **Lien** | https://www.data.gouv.fr/datasets/donnees-du-temps-densoleillement-par-departements-en-france |
| **Contenu** | Nombre de jours d'ensoleillement par an par département |
| **Granularité** | Département (métropole uniquement — 92 départements, pas de DOM) |
| **Format** | CSV — 1 fichier léger (`temps-densoleillement-par-an-par-departement-feuille-1.csv`, 1.4 KB) |
| **Intérêt** | Critère de cadre de vie direct — le sud vs le nord de la France |

#### Colonnes (vérifiées sur `temps-densoleillement-par-an-par-departement-feuille-1.csv`)

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `Départements` | Nom du département (texte, ex: `Ain`) | Oui (jointure par nom → code) |
| `Temps d'enseillement (jours/an)` | Jours ensoleillés par an (entier, 107-253) | Oui (→ `jours_ensoleillement`) |

> **Attention** : pas de `code_departement` dans le fichier — jointure par **nom** du département (nécessite un mapping nom → code via COG).
> **Jointure** : nom département → code département → toutes les communes du département héritent de la valeur.
> **Typo** dans le header : "enseillement" au lieu de "ensoleillement" — à gérer au parsing.

### Données climatologiques quotidiennes · `P2` `✅`

| | |
|---|---|
| **Source** | Météo-France |
| **Lien** | https://www.data.gouv.fr/datasets/donnees-climatologiques-de-base-quotidiennes |
| **Contenu** | Températures (min, max, moyenne), précipitations, vent par station depuis leur ouverture |
| **Granularité** | Station météo (jointure spatiale → commune la plus proche) |
| **Format** | CSV.gz — 626 fichiers, organisés par département et période |
| **Fichiers utiles** | `Q_{DEP}_previous-1950-2024_RR-T-Vent.csv.gz` (un par département) |
| **Notes** | Alternative plus fine si on veut la pluviométrie à la commune — complexité élevée |

#### Colonnes fichiers RR-T-Vent (vérifiées sur `Q_01_previous-1950-2024_RR-T-Vent.csv.gz`)

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `NUM_POSTE` | Identifiant station (8 chars) | Oui (jointure → commune) |
| `NOM_USUEL` | Nom de la station | Non |
| `LAT`, `LON` | Coordonnées WGS-84 | Oui (jointure spatiale) |
| `ALTI` | Altitude (m) | Non |
| `AAAAMMJJ` | Date (format `20241231`) | Oui (filtre année) |
| `RR` | Précipitations quotidiennes (mm) | Oui (→ somme annuelle) |
| `QRR` | Flag qualité RR (0=bon, 9=absent) | Oui (filtre qualité) |
| `TN` | Température minimale (°C) | Non |
| `TX` | Température maximale (°C) | Non |
| `TM` | Température moyenne (°C) | Non |
| `FFM` | Vitesse vent moyenne (m/s) | Non |

> **⚠️ `INST` (insolation) absente** : les fichiers `RR-T-Vent` ne contiennent que précipitations, température et vent. L'insolation est dans les fichiers `*_autres-parametres.csv.gz` (autre téléchargement).
> **Colonnes "Q"** : flags qualité (0 = bon, 1 = suspect, 2 = douteux, 9 = absent) — filtrer `Q* != 9`.

### Sources météo exclues

#### ~~Fiches climatologiques~~ · `EXCLU`

> **Raison** : redondant avec les données climatologiques quotidiennes (même source, synthèse vs détail).

---

## 12. Eau : qualité et prix

### Tarifs eau potable et assainissement (SISPEA) · `P1` `✅`

| | |
|---|---|
| **Source** | SISPEA — Observatoire national des services d'eau et d'assainissement (OFB) |
| **Lien** | https://www.services.eaufrance.fr/donnees/telechargement |
| **Contenu** | Tarifs eau potable (AEP) et assainissement collectif (AC) par commune, pour une consommation de 120 m³/an |
| **Granularité** | Commune |
| **Format** | XLS — 2 fichiers par année, 3 feuilles chacun |
| **Fichiers** | `tarifs_AEP_2024.xls` (~17 MB) + `tarifs_AC_2024.xls` (~13 MB) |
| **Couverture** | France entière — ~33 600 communes, 97 départements (métropole + DOM), données 2008-2025 |
| **Intérêt** | Coût de vie local — varie fortement d'une commune à l'autre |

> **⚠️ Remplace** l'ancien dataset data.gouv.fr "Tarif de l'eau potable et de l'assainissement par commune" qui ne couvrait que la Métropole Aix-Marseille-Provence (92 communes sur 3 départements).

#### Structure des fichiers XLS

Chaque fichier (AEP et AC) contient 3 feuilles :

| Feuille | Lignes (AEP) | Colonnes | Description |
|---------|--------------|----------|-------------|
| `Metadonnees` | 15 | 6 | Description du dataset |
| `Détail tarifaire` | 9 622 | 90 | Tarifs détaillés par entité de gestion (tranches, bornes) |
| `Zones tarifaires` | 35 452 | 28 | **Jointure commune → tarif** (feuille principale) |

#### Colonnes (vérifiées sur `tarifs_AEP_2024.xls`, feuille `Zones tarifaires`)

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `Code INSEE de la commune adhérente` | Code commune INSEE (5 chars) | Oui (→ `code_commune`) |
| `Nom de la commune adhérente` | Nom de la commune | Non |
| `DPT de la commune` | Code département | Non (déjà dans communes) |
| `Population de la commune` | Population communale | Non (déjà via INSEE) |
| `Tarif zone tarifaire 1` | Prix eau potable en €/m³ TTC | Oui (→ `tarif_eau`) |
| `Compétence` | Type de service (eau potable / assainissement) | Non (implicite par fichier) |
| `Mode de gestion` | Régie / Délégation / etc. | Non |

> **Note processing** : pour obtenir le tarif assainissement, il faut joindre `Zones tarifaires` de `tarifs_AC_2024.xls` sur le même `Code INSEE`. Le prix final = `tarif_eau` (AEP) + `tarif_assainissement` (AC).
>
> **Exemple** : Oncieu (01279) — Eau potable : 2.12 €/m³, population : 77 habitants.

### Sources eau exclues

#### ~~Tarif eau Métropole Aix-Marseille-Provence~~ · `EXCLU`

> **Raison** : couverture limitée à 92 communes (départements 13, 83, 84). Remplacé par le dataset SISPEA national.

#### ~~Contrôle sanitaire de l'eau (ARS)~~ · `EXCLU`

> **Raison** : données trop détaillées (analyses chimiques bactériologie/nitrates/pesticides). Pas exploitable simplement pour un indicateur communal.

#### ~~Prix global de l'eau potable (data.gouv.fr)~~ · `EXCLU`

> **Raison** : dataset départemental (Saône-et-Loire), pas de couverture nationale.

---

## 13. Couverture internet

### Ma Connexion Internet (MCI) · `P1` `✅`

| | |
|---|---|
| **Source** | ARCEP (Autorité de régulation des communications électroniques) |
| **Lien** | https://www.data.gouv.fr/datasets/ma-connexion-internet |
| **Contenu** | Statistiques d'éligibilité internet par commune : fibre, DSL, câble, 4G fixe |
| **Granularité** | Commune (fichiers agrégés disponibles directement) |
| **Format** | CSV |
| **MAJ** | Trimestrielle — **dernières données : T3 2025** (décembre 2025) |
| **Intérêt** | Le débit internet est un critère majeur de choix de logement, surtout post-COVID (télétravail) |

#### Fichiers disponibles au niveau commune (T3 2025)

| Fichier | Contenu |
|---------|---------|
| `commune.csv` | Stats globales par commune (nb locaux) |
| `commune_techno.csv` | Éligibilité par technologie (DSL, câble, fibre, 4G fixe) |
| `commune_debit.csv` | Éligibilité par classe de débit |
| `commune_meilleure_techno_thd.csv` | Meilleure techno THD disponible par commune |

#### Colonnes de `commune.csv` (vérifiées sur fichier T3 2025)

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `code_insee` | Code commune INSEE (5 chars) | Oui (→ `code_commune`) |
| `nom_com` | Nom de la commune | Non |
| `code_dep` | Code département | Non |
| `code_reg` | Code région | Non |
| `nbr` | Nombre de locaux (compteur unique) | Oui |
| `type` | Type de comptage (valeur unique : `all`) | Non |
| `date` | Date des données (ex: `2025-09-30`) | Non |

> **⚠️ Fichier simplifié** : `commune.csv` ne contient qu'un compteur `nbr` avec `type=all` — il n'y a **pas** de ventilation fibre/THD/HD dans ce fichier.
> **Pour les indicateurs fibre/THD**, il faut utiliser `commune_techno.csv` (éligibilité par technologie) qui n'a pas encore été téléchargé.
> **Couverture** : 34 877 communes, 103 départements (métropole + DOM).
> **Jointure** : `code_insee` (pas `code_commune`).

---

## 14. Référentiels géographiques

### Contours administratifs · `P0` `✅`

| | |
|---|---|
| **Source** | Etalab / IGN |
| **Lien** | https://www.data.gouv.fr/datasets/contours-administratifs |
| **Contenu** | Contours communes, départements, régions, EPCI |
| **Format** | GeoJSON (plusieurs niveaux de simplification : 5m, 50m, 100m, 1000m) |
| **Fichiers 2025** | https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/geojson/ |
| **Tâche** | P1-1

#### Structure GeoJSON (vérifiée sur `communes-5m.geojson.gz`)

```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "properties": {
      "code": "01001",          // → code_commune
      "nom": "L'Abergement-Clémenciat",
      "departement": "01",      // → code_departement
      "region": "84",           // → code_region
      "epci": "200069193"       // Code EPCI
    },
    "geometry": { "type": "Polygon", "coordinates": [...] }
  }]
}
```

> Le fichier `-5m` contient ~35K features (toutes les communes) avec géométries simplifiées à 5m de précision.

### Contours simplifiés (DOM rapprochés) · `P0` `⬜`

| | |
|---|---|
| **Lien** | https://www.data.gouv.fr/datasets/contours-des-communes-de-france-simplifie-avec-regions-et-departement-doutre-mer-rapproches |
| **Notes** | DOM rapprochés de la métropole — pratique pour les cartes web |

### Correspondance code postal / code INSEE · `P0` `✅`

| | |
|---|---|
| **Lien** | https://www.data.gouv.fr/datasets/base-officielle-des-codes-postaux |
| **Source** | La Poste |
| **Notes** | Base officielle maintenue à jour (la table de 2016 sur data.gouv.fr est obsolète — nombreuses fusions de communes depuis) |

#### Colonnes (vérifiées sur `019HexaSmal.csv` — séparateur `;`, encodage Latin-1)

| Colonne source | Description | Utilisée dans Homepedia |
|----------------|-------------|------------------------|
| `Code_commune_INSEE` | Code commune INSEE (5 chars) | Oui (→ `code_commune`) |
| `Nom_de_la_commune` | Nom de la commune (en majuscules) | Non |
| `Code_postal` | Code postal | Oui (→ `code_postal`) |
| `Libellé_d_acheminement` | Libellé postal d'acheminement | Non |
| `Ligne_5` | Complément d'adresse (souvent vide) | Non |

> **Attention** : encodage **Latin-1** (pas UTF-8) — les caractères accentués sont cassés si lu en UTF-8.

---

## 15. Scraping (données non-tabulaires)

> **Obligatoire** dans le projet — alimente le NLP, le word cloud (P5-13), le router `reviews` (P4-6), et les `listings` JSONB.

### ville-ideale.fr · `P0` `⬜`

| | |
|---|---|
| **Outil** | Scrapy |
| **Contenu** | Notes sur 8 critères + commentaires texte par ville |
| **Volume estimé** | ~8 500 villes, ~91 000 avis |
| **Stockage** | `data/raw/ville_ideale/` (JSON) → PostgreSQL JSONB (`city_reviews`) |
| **Tâche** | P1-8 (XL), P2-4, P4-6 |
| **Contraintes** | Rate-limit strict (1 req/s), respect robots.txt |

### pap.fr · `P1` `⬜`

| | |
|---|---|
| **Outil** | BeautifulSoup |
| **Contenu** | Annonces immobilières : prix, surface, localisation, type, description, DPE |
| **Volume estimé** | Échantillon ~5 000-10 000 annonces |
| **Stockage** | `data/raw/pap/` (JSON) → PostgreSQL JSONB (`listings`) |
| **Tâche** | P1-9 (L) |
| **Contraintes** | Rate-limit strict, respect CGU |

---

## Clé de jointure universelle

Tous ces datasets sont reliés via le **`code_commune` INSEE** (5 caractères).

Attention aux cas particuliers :
- **Paris, Lyon, Marseille** : arrondissements avec codes spécifiques
- **Fusions de communes** : codes qui changent au fil du temps — utiliser le COG (Code Officiel Géographique) historique

---

## Résumé par priorité

### P0 — Obligatoire (coeur du projet)

| Source | Catégorie | Volume | Colonnes | Tâche |
|--------|-----------|--------|----------|-------|
| DVF (Geo-DVF + brut) | Immobilier | ~25-30M lignes | ✅ | P1-2 |
| DPE (nouveau + ancien) | Énergie | ~9M + ~10.7M lignes | ✅ | P1-3 |
| Carte des loyers (×4) | Immobilier | ~35K lignes/fichier | ✅ | — |
| BPE | Équipements | ~2M lignes | ✅ | P1-4 |
| FiLoSoFi | Socio-économique | IRIS → commune | ✅ | P1-5 |
| Populations historiques | Démographie | 1 fichier xlsx | ✅ | P1-5 |
| France Travail | Emploi | 2M lignes (T4 annuel) | ✅ | P1-5 |
| Contours GeoJSON | Référentiel | ~35K communes | ✅ | P1-1 |
| COG + CP/INSEE | Référentiel | — | ✅ | P1-1 |
| ville-ideale.fr (scraping) | Avis | ~91K avis | ⬜ | P1-8 |

### P1 — Forte valeur ajoutée

| Source | Catégorie | Colonnes | Tâche |
|--------|-----------|----------|-------|
| Délinquance (SSMSI) | Sécurité | ✅ | P1-6 |
| DNB + IVAL | Éducation | ✅ | P1-7 |
| Impôts locaux (REI) | Fiscalité | ✅ | — |
| LOVAC | Immobilier | ✅ | — |
| Zonage ABC | Immobilier | ✅ | — |
| pap.fr (scraping) | Annonces | ⬜ | P1-9 |
| Ma Connexion Internet | Infrastructure | ✅ | `commune.csv` vérifié, `commune_techno.csv` à télécharger |
| API Géorisques | Risques | ⬜ | — |
| Ensoleillement par département | Climat | ✅ | Promu P1 (jours/an, 92 depts) |
| Tarifs eau SISPEA | Coût de vie | ✅ | Source changée (SISPEA remplace Aix-Marseille) |

### P2 — Optionnel

| Source | Catégorie | Colonnes |
|--------|-----------|----------|
| RPLS (logements sociaux) | Immobilier | ✅ |
| Comptes des communes | Finances | ✅ |
| Nuance politique | Élections | ⬜ |
| Déplacements domicile-travail | Transport | ✅ | Format long vérifié |
| Données climatologiques quotidiennes | Climat | ✅ | `INST` absente des fichiers RR-T-Vent |
