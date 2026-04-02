# Sources de données -- Digest

> Version condensée de [`datagouv-sources.md`](datagouv-sources.md).
> Consulter l'original pour les détails : colonnes, formats, pièges de parsing.

---

## Vue d'ensemble

| Source | Catégorie | Priorité | Volume approx. | Colonnes | Clé de jointure | Description |
|--------|-----------|----------|----------------|----------|-----------------|-------------|
| Cadastre (parcelles) | Référentiel | P0 | ~70M parcelles | ✅ | `commune` (code INSEE) | Contours des parcelles cadastrales (section, numéro, contenance) |
| DVF (Geo-DVF + brut) | Immobilier | P0 | ~25-30M lignes | ✅ | `code_commune` | Transactions immobilières (prix, surface, type, localisation) |
| DPE (nouveau + ancien) | Énergie | P0 | ~9M + ~10.7M lignes | ✅ | `code_insee_ban` / `code_insee_commune` | Classes énergétiques A-G, consommation, émissions GES |
| Carte des loyers (×4 fichiers) | Immobilier | P0 | ~35K lignes/fichier | ✅ | `INSEE_C` | Loyer prédit au m² par commune avec intervalle de confiance |
| BPE | Équipements | P0 | ~2M lignes | ✅ | `DEPCOM` | Inventaire équipements/services (santé, éducation, transport, commerces) |
| FiLoSoFi | Socio-éco | P0 | IRIS → commune | ✅ | `Commune ou ARM` | Revenu médian, taux de pauvreté, distribution des revenus |
| Populations historiques | Démographie | P0 | 1 fichier xlsx | ✅ | `code_commune` | Populations communales 1876-2023 |
| France Travail | Emploi | P0 | ~2M lignes | ✅ | `Code commune` | Demandeurs d'emploi par commune (T4 annuel, 2015-2024) |
| Contours GeoJSON | Référentiel | P0 | ~35K communes | ✅ | `code` (propriété GeoJSON) | Contours communes, départements, régions |
| Contours DOM rapprochés | Référentiel | P0 | - | ⬜ | `code` | Contours avec DOM rapprochés de la métropole |
| CP / INSEE | Référentiel | P0 | - | ✅ | `Code_commune_INSEE` | Correspondance code postal ↔ code commune |
| ville-ideale.fr (scraping) | Avis | P0 | ~91K avis, ~8 500 villes | ⬜ | nom ville | Notes sur 8 critères + commentaires texte |
| LOVAC | Immobilier | P1 | ~35K lignes | ✅ | `CODGEO_25` | Logements vacants du parc privé (2020-2025) |
| Zonage ABC | Immobilier | P1 | ~35K lignes | ✅ | `CODGEO` | Classification tension immobilière (A, Abis, B1, B2, C) |
| Impôts locaux (REI) | Fiscalité | P1 | ~35K lignes × 1101 col | ✅ | `IDCOM` | Taux taxe foncière par commune |
| Délinquance (SSMSI) | Sécurité | P1 | ~4.7M lignes | ✅ | `CODGEO_2025` | 15 indicateurs crimes/délits depuis 2016 |
| DNB (Brevet) | Éducation | P1 | - | ✅ | `Commune` | Taux de réussite et mentions par collège |
| IVAL (Lycées) | Éducation | P1 | - | ✅ | `Code commune` | Taux de réussite bac, valeur ajoutée par lycée |
| Ma Connexion Internet | Infrastructure | P1 | ~35K communes | ✅ | `code_insee` | Éligibilité fibre, DSL, câble, 4G fixe |
| APL (DREES) | Santé | P1 | - | ⬜ | `code_commune` | Accessibilité potentielle localisée aux médecins généralistes |
| API Géorisques | Risques | P1 | API REST | ⬜ | commune/adresse | Risques naturels et technologiques (inondation, séisme, radon...) |
| Ensoleillement | Climat | P1 | 92 lignes | ✅ | nom département | Jours d'ensoleillement par an par département |
| Tarifs eau SISPEA | Coût de vie | P1 | ~33 600 communes | ✅ | `Code INSEE de la commune adhérente` | Prix eau potable + assainissement par commune |
| pap.fr (scraping) | Annonces | P1 | ~5-10K annonces | ⬜ | localisation | Annonces immobilières (prix, surface, DPE) |
| RPLS | Immobilier | P2 | - | ✅ | `Code Commune` | Parc locatif social détaillé au logement |
| Comptes des communes | Finances | P2 | ~22M lignes (6.8 GB) | ✅ | `Code Insee 2024 Commune` | Finances locales 2017-2024 (~30 agrégats) |
| Nuance politique | Élections | P2 | - | ⬜ | code INSEE | Nuance politique du maire (municipales 2020) |
| Déplacements domicile-travail | Transport | P2 | ~1.2M lignes | ✅ | `GEO` (filtrer `COM`) | Modes de transport domicile-travail par commune |
| Données climatologiques | Climat | P2 | 626 fichiers .gz | ✅ | `NUM_POSTE` (jointure spatiale) | Températures, précipitations, vent par station |

---

## Pipeline par priorité

### P0 -- Obligatoire

| Source | Format | URL |
|--------|--------|-----|
| Cadastre (parcelles) | GeoJSON (gzip, par dept) | https://cadastre.data.gouv.fr/bundler/cadastre-etalab/departements/{dept}/geojson/parcelles |
| DVF brut (DGFiP) | CSV (`\|`, Latin-1) | https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres |
| Geo-DVF (Etalab) | CSV (UTF-8) | https://files.data.gouv.fr/geo-dvf/latest/csv/ |
| DPE nouveau (depuis juil. 2021) | CSV | https://www.data.gouv.fr/datasets/dpe-logements-existants-depuis-juillet-2021 |
| DPE ancien (avant juil. 2021) | dump MySQL | https://www.data.gouv.fr/datasets/dpe-logements-avant-juillet-2021 |
| Carte des loyers | CSV (`;`) | https://www.data.gouv.fr/datasets/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025 |
| BPE | CSV (`;`) | https://www.data.gouv.fr/datasets/base-permanente-des-equipements-1 |
| FiLoSoFi | XLSX | https://www.data.gouv.fr/fr/datasets/revenus-localises-sociaux-et-fiscaux-dispositif-filosofi/ |
| Populations historiques | XLSX | https://www.insee.fr/fr/statistiques/3698339 |
| France Travail | CSV (`;`, BOM UTF-8) | https://www.data.gouv.fr/en/datasets/demandeurs-demploi-inscrits-a-france-travail-donnees-communales-trimestrielles-brutes/ |
| Contours GeoJSON | GeoJSON | https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/geojson/ |
| Contours DOM rapprochés | GeoJSON | https://www.data.gouv.fr/datasets/contours-des-communes-de-france-simplifie-avec-regions-et-departement-doutre-mer-rapproches |
| CP / INSEE | CSV (`;`, Latin-1) | https://www.data.gouv.fr/datasets/base-officielle-des-codes-postaux |
| ville-ideale.fr | Scraping (Scrapy) | https://www.ville-ideale.fr |

### P1 -- Forte valeur

| Source | Format | URL |
|--------|--------|-----|
| LOVAC | CSV (`;`) | https://www.data.gouv.fr/datasets/logements-vacants-du-parc-prive-par-commune-departement-region |
| Zonage ABC | CSV (`;`) | https://www.data.gouv.fr/datasets/liste-des-communes-par-zone-du-dispositif-pinel |
| Impôts locaux (REI) | CSV (`;`, Latin-1) -- ZIP annuel | https://www.data.gouv.fr/datasets/impots-locaux-fichier-de-recensement-des-elements-dimposition-a-la-fiscalite-directe-locale-rei-4 |
| Délinquance | CSV (format long) | https://www.data.gouv.fr/datasets/bases-statistiques-communale-departementale-et-regionale-de-la-delinquance-enregistree-par-la-police-et-la-gendarmerie-nationales |
| DNB (Brevet) | CSV (`;`) | https://www.data.gouv.fr/datasets/diplome-national-du-brevet-par-etablissement-1 |
| IVAL (Lycées) | CSV (`;`) | https://www.data.gouv.fr/datasets/indicateurs-de-valeur-ajoutee-des-lycees-denseignement-general-et-technologique-ancien |
| Ma Connexion Internet | CSV | https://www.data.gouv.fr/datasets/ma-connexion-internet |
| APL (DREES) | XLSX | https://www.data.gouv.fr/datasets/laccessibilite-potentielle-localisee-apl |
| API Géorisques | API REST (JSON) | https://www.data.gouv.fr/dataservices/api-georisques |
| Ensoleillement | CSV | https://www.data.gouv.fr/datasets/donnees-du-temps-densoleillement-par-departements-en-france |
| Tarifs eau SISPEA | XLS | https://www.services.eaufrance.fr/donnees/telechargement |
| pap.fr | Scraping (BeautifulSoup) | https://www.pap.fr |

### P2 -- Optionnel

| Source | Format | URL |
|--------|--------|-----|
| RPLS (logements sociaux) | CSV (`;`) | https://www.data.gouv.fr/datasets/donnees-detaillees-au-logement-du-repertoire-des-logements-locatifs-des-bailleurs-sociaux-rpls |
| Comptes des communes | CSV (`;`, BOM UTF-8) | https://www.data.gouv.fr/datasets/comptes-des-communes-2017-2024 |
| Nuance politique | CSV (UTF-8) | https://www.data.gouv.fr/datasets/communes-enrichies-avec-la-nuance-politique-france |
| Déplacements domicile-travail | CSV (format long) | https://www.data.gouv.fr/fr/datasets/deplacements-domicile-travail/ |
| Données climatologiques | CSV.gz (626 fichiers) | https://www.data.gouv.fr/datasets/donnees-climatologiques-de-base-quotidiennes |

---

## Sources exclues

| Source | Raison |
|--------|--------|
| Nombre de ventes (maisons/apparts anciens) | Granularité France entière uniquement, pas communale -- DVF couvre déjà |
| Permis d'aménager (Sitadel) | Volume trop faible (~2 100 lignes), pas les permis de construire |
| Data INSEE communes | Abandonné (dernière MAJ déc. 2014) |
| Marché du travail (INSEE BDM) | Granularité départementale/régionale, pas communale |
| Enquête emploi en continu | Granularité nationale uniquement |
| Données IRIS / zone emploi | Obsolète (dernière MAJ 2022) |
| GTFS | Format complexe multi-fichiers, couverture incomplète -- BPE couvre gares/arrêts |
| Démographie médecins (RPPS) | Redondant avec BPE + APL |
| Démographie pros santé (2012-2024) | Granularité départementale, pas communale |
| Pros santé libéraux | Granularité départementale/régionale |
| Données électorales détaillées | Trop granulaire (bureau de vote), pas de lien immobilier |
| Zones inondables (TRI) | Format SHP complexe, 124 territoires seulement -- Géorisques agrège déjà |
| PPRN (Plans Prévention) | Redondant avec API Géorisques |
| Cartes du bruit / PEB aéroports | Format SHP, couverture partielle, gain marginal |
| Fiches climatologiques | Redondant avec données climatologiques quotidiennes |
| Tarif eau Aix-Marseille-Provence | Couverture limitée à 92 communes -- remplacé par SISPEA national |
| Contrôle sanitaire eau (ARS) | Trop détaillé (analyses chimiques), pas exploitable simplement |
| Prix global eau potable (data.gouv.fr) | Dataset départemental (Saône-et-Loire), pas national |

---

## Structure de téléchargement par source

> Combien de fichiers faut-il télécharger pour couvrir l'historique complet ?

### Sources multi-fichiers (téléchargement complexe)

| Source | Nb fichiers | Pattern | Détail |
|--------|------------|---------|--------|
| **DVF** | ~12+ | 1 fichier/an | Geo-DVF (2020-2025, UTF-8) + DVF brut (2014-2019, Latin-1 `\|`) — 2 sources distinctes à fusionner |
| **DPE** | 2 | Split format | Nouveau (post juil. 2021, CSV ~9M) + Ancien (pré-2021, dump MySQL ~10.7M) — formats incompatibles |
| **Carte des loyers** | 4 | 1 fichier/type | `pred-app-mef-dhup.csv`, `pred-mai-mef-dhup.csv`, `pred-app3-mef-dhup.csv`, `pred-app12-mef-dhup.csv` |
| **Contours GeoJSON** | 3-6 | 1 fichier/niveau géo | communes, départements, régions × niveaux de simplification (5m, 50m, 100m) |
| **REI (Impôts)** | 1/an | ZIP annuel | `REI-{YEAR}-fichier-notice-trace.zip` — 1 ZIP par année à extraire |
| **Ma Connexion Internet** | 4 | 1 fichier/type | `commune.csv`, `commune_techno.csv`, `commune_debit.csv`, `commune_meilleure_techno_thd.csv` |
| **Tarifs eau (SISPEA)** | 2/an | 1 fichier/type/an | `tarifs_AEP_{YEAR}.xls` (eau potable ~17 MB) + `tarifs_AC_{YEAR}.xls` (assainissement ~13 MB) |
| **Données climatologiques** | **~626** | 1 fichier/dept/période | `Q_{DEP}_previous-1950-2024_RR-T-Vent.csv.gz` — massif, P2 |

### Sources fichier unique (mais volume historique intégré)

| Source | Fichiers | Période couverte | Volume |
|--------|----------|-----------------|--------|
| **BPE** | 1 CSV | Dernier millésime uniquement | ~2M lignes |
| **FiLoSoFi** | 1 XLSX | Dernière année (IRIS → commune) | ~120 MB |
| **Populations** | 1 XLSX | 1968-2023 (toutes années dans le fichier) | ~6 MB |
| **France Travail** | 1 CSV | 2015-2024 (format long : commune × trimestre) | ~2M lignes |
| **Criminalité** | 1 Parquet | 2016-2025 (format long : commune × année × indicateur) | ~4.7M lignes |
| **Comptes communes** | 1 CSV | 2017-2024 (format long) | **6.8 GB**, 22M lignes |
| **Navettes** | 1 ZIP | 2022 (format long multi-niveaux) | ~70 MB, 1.2M lignes |
| **LOVAC** | 1 CSV | 2020-2025 | ~35K lignes |
| **Zonage ABC** | 1 CSV | Dernière version | ~35K lignes |
| **Ensoleillement** | 1 CSV | Statique | 92 lignes |
| **Nuance politique** | 1 CSV | Municipales 2020 | ~35K lignes |

### Sources sans fichier (API / scraping)

| Source | Mode | Volume estimé |
|--------|------|--------------|
| **API Géorisques** | API REST (1 appel/commune, ~35K appels batch) | ~35K réponses JSON |
| **ville-ideale.fr** | Scraping HTML (~8 500 pages villes) | ~91K avis |
| **pap.fr** | Scraping HTML | ~5-10K annonces |

---

## Notes techniques rapides

- **Clé de jointure universelle** : `code_commune` INSEE (5 caractères) -- chaque source a son propre nom de colonne (voir tableau ci-dessus)
- **Paris / Lyon / Marseille** : arrondissements avec codes spécifiques -- attention aux jointures
- **Fusions de communes** : codes qui changent au fil du temps -- utiliser le COG historique
- **Encodages** :
  - **Latin-1** : DVF brut, CP/INSEE, REI (impôts locaux)
  - **BOM UTF-8** (`\xEF\xBB\xBF` devant la 1ère colonne) : France Travail, Comptes des communes
  - **Typo header** : ensoleillement écrit "enseillement" dans le CSV source
- **DVF brut vs Geo-DVF** : Geo-DVF couvre 2020-2025 uniquement ; pour 2014-2019, utiliser le DVF brut (séparateur `|`, `Code commune` sur 3 chars à concaténer avec `Code departement`)
- **DPE ancien** : dump MySQL (pas CSV), FK vers tables de référence -- nécessite conversion
- **DPE nouveau** : ~200 colonnes, certaines avec espaces dans le nom (`conso_5 usages_par_m2_ef`)
