# Source de données : ville-ideale.fr — Homepedia

> Documentation détaillée de la source ville-ideale.fr pour le scraping
> d'avis et de notes sur les villes françaises.

---

## Vue d'ensemble

| | |
|---|---|
| **Site** | https://www.ville-ideale.fr |
| **Type** | Plateforme participative de notation des villes françaises |
| **Volume** | ~91 000 notations sur ~8 500 villes |
| **Méthode d'accès** | Scraping (pas d'API officielle) |
| **Technologie recommandée** | Scrapy (déjà prévu dans le stack Homepedia) |
| **Stockage cible** | PostgreSQL (JSONB) — schéma variable des avis |

---

## Données disponibles

### 1. Notes par critère (quantitatif)

Chaque ville dispose de notes sur **9 critères**, notés de **0 à 10** par les utilisateurs :

| # | Critère | Description |
|---|---------|-------------|
| 1 | **Environnement** | Qualité de l'air, gestion des déchets, parcs et espaces verts |
| 2 | **Transports** | Infrastructure routière, réseaux de mobilité, transports en commun |
| 3 | **Sécurité** | Services de police, niveau de criminalité ressenti |
| 4 | **Santé** | Accès aux établissements médicaux, médecins, pharmacies |
| 5 | **Sports et loisirs** | Installations sportives, activités associatives |
| 6 | **Culture** | Cinémas, musées, patrimoine, événements culturels |
| 7 | **Enseignement** | Écoles, collèges, lycées, formations |
| 8 | **Commerces** | Accès aux services commerciaux, diversité des commerces |
| 9 | **Qualité de vie** | Bien-être général ressenti à vivre dans la ville |

**Moyennes nationales** (villes avec 100+ avis) :

| Critère | Moyenne /10 |
|---------|-------------|
| Sports et loisirs | 6,78 |
| Transports | 6,41 |
| Enseignement | 6,40 |
| Culture | 6,39 |
| Santé | 6,30 |
| Commerces | 6,17 |
| Environnement | 6,09 |
| Sécurité | 5,47 |

### 2. Avis textuels (qualitatif)

Chaque notation comprend des **commentaires textuels** :

| Champ | Description |
|-------|-------------|
| **Points positifs** | Texte libre sur les atouts de la ville |
| **Points négatifs** | Texte libre sur les défauts de la ville |
| **Longueur** | Entre 300 et 3 000 caractères (positifs + négatifs combinés) |
| **Pseudonyme** | Nom affiché de l'auteur |
| **Statut** | Habitant ou ancien résident |
| **Date** | Timestamp de validation de l'avis |

### 3. Données agrégées par ville

| Donnée | Description |
|--------|-------------|
| **Note globale** | Moyenne des 9 critères |
| **Nombre d'avis** | Total de notations reçues |
| **Nom de la ville** | Avec code postal |
| **Rang** | Position dans les classements (général + par critère) |

---

## Structure du site (URLs)

### Pages principales

| Page | URL |
|------|-----|
| Accueil | https://www.ville-ideale.fr/ |
| Classements par critère | https://www.ville-ideale.fr/classements.php |
| Palmarès | https://www.ville-ideale.fr/palmares.php |
| Villes par département | https://www.ville-ideale.fr/villespardepts.php |

### URL d'une ville

Format : `https://www.ville-ideale.fr/{nom-ville}_{code_insee}`

Exemples :
- Angers : `https://www.ville-ideale.fr/angers_49007`
- Metz : `https://www.ville-ideale.fr/metz_57463`
- Paris 15e : `https://www.ville-ideale.fr/paris-15e-arrondissement_75115`

**Conventions** :
- Nom en minuscules
- Espaces remplacés par des tirets `-`
- Séparateur nom/code : underscore `_`
- Le code correspond au **code INSEE** (5 caractères) → jointure directe avec `code_commune`

### Navigation par département

La page `/villespardepts.php` utilise du JavaScript dynamique (`affdept('code', 'nom')`) pour charger les listes de villes. Le scraper doit gérer ce chargement dynamique ou appeler directement les endpoints sous-jacents.

---

## Filtres et classements disponibles

### Par taille de population

| Filtre | Description |
|--------|-------------|
| Moins de 5 000 habitants | Petites communes rurales |
| 5 000 à 10 000 habitants | Petites villes |
| 10 000 à 20 000 habitants | Villes moyennes basses |
| 20 000 à 50 000 habitants | Villes moyennes |
| 50 000 à 100 000 habitants | Grandes villes |
| Plus de 100 000 habitants | Métropoles |

### Par critère

Classements "meilleures" et "pires" villes disponibles pour chacun des 9 critères individuellement.

### Fiabilité

Le site considère les résultats fiables à partir de **100 avis minimum** par ville (~237 villes atteignent ce seuil).

---

## Stratégie de scraping recommandée

### Architecture

```
src/scraping/
  ville_ideale/
    spiders/
      cities_spider.py      # Liste des villes par département
      reviews_spider.py      # Avis et notes par ville
    items.py                 # Définition des items Scrapy
    pipelines.py             # Pipeline PostgreSQL (JSONB)
```

### Données à extraire

#### Par ville (table ou document JSONB)

```json
{
  "code_commune": "49007",
  "nom_ville": "Angers",
  "note_globale": 7.85,
  "nb_avis": 200,
  "notes": {
    "environnement": 7.2,
    "transports": 6.8,
    "securite": 6.5,
    "sante": 7.0,
    "sports_loisirs": 7.5,
    "culture": 7.8,
    "enseignement": 7.3,
    "commerces": 6.9,
    "qualite_vie": 7.6
  },
  "date_scraping": "2026-03-05"
}
```

#### Par avis (document JSONB)

```json
{
  "code_commune": "49007",
  "pseudonyme": "JeanDupont",
  "statut": "habitant",
  "date_avis": "2026-02-15",
  "points_positifs": "...",
  "points_negatifs": "...",
  "notes": {
    "environnement": 8,
    "transports": 7,
    "securite": 6,
    "sante": 7,
    "sports_loisirs": 8,
    "culture": 9,
    "enseignement": 7,
    "commerces": 7,
    "qualite_vie": 8
  }
}
```

### Points d'attention techniques

| Aspect | Détail |
|--------|--------|
| **JavaScript dynamique** | La navigation par département charge les villes via JS → utiliser Splash ou reconstruire les requêtes AJAX |
| **Rate limiting** | Respecter un délai entre requêtes (1-2s minimum) pour ne pas surcharger le serveur |
| **robots.txt** | Vérifier les règles du `robots.txt` avant de scraper |
| **Encodage** | UTF-8, attention aux caractères spéciaux dans les noms de villes |
| **Pagination** | Les avis sont potentiellement paginés sur les grandes villes |
| **Validation** | Les avis sont validés manuellement → données de meilleure qualité que d'autres sources |

---

## Intérêt pour Homepedia

### Valeur ajoutée unique

ville-ideale.fr est la **seule source de données subjectives** du projet. Toutes les autres sources (DVF, DPE, INSEE, etc.) sont des données objectives/quantitatives. Les avis apportent :

- **Le ressenti des habitants** — complémentaire aux statistiques officielles
- **Des notes par critère** — permettent un scoring multi-dimensionnel de la qualité de vie
- **Du texte libre** — exploitable en NLP (analyse de sentiment avec spaCy/CamemBERT, word clouds)

### Croisements possibles avec les données officielles

| Critère ville-ideale | Source officielle à croiser | Analyse |
|----------------------|---------------------------|---------|
| Sécurité (ressenti) | Bases délinquance SSMSI | Corrélation ressenti vs statistiques réelles |
| Transports (ressenti) | BPE / transport.data.gouv.fr | Satisfaction vs offre de transport |
| Santé (ressenti) | RPPS / densité médicale | Satisfaction vs densité de médecins |
| Environnement (ressenti) | DPE / qualité de l'eau | Perception vs mesures objectives |
| Commerces (ressenti) | BPE (catégories commerces) | Satisfaction vs nombre d'équipements |
| Enseignement (ressenti) | DNB / IVAL | Satisfaction vs résultats scolaires |

### Traitement NLP prévu

| Analyse | Outil | Sortie |
|---------|-------|--------|
| Analyse de sentiment | spaCy (fr_core_news_md) / CamemBERT | Score positif/négatif par avis |
| Extraction de thèmes | spaCy NER + règles | Thèmes récurrents par ville |
| Word clouds | wordcloud (Python) | Nuages de mots par ville (stockés en JSONB) |
| Résumé automatique | CamemBERT | Synthèse des points positifs/négatifs |

---

## Clé de jointure

Le code dans l'URL des villes correspond au **code INSEE** (`code_commune`), ce qui permet une **jointure directe** avec toutes les autres sources de données du projet.

Exemple : `/angers_49007` → `code_commune = "49007"`

---

## Références externes

| Ressource | Lien |
|-----------|------|
| Site officiel | https://www.ville-ideale.fr |
| Classements | https://www.ville-ideale.fr/classements.php |
| Palmarès | https://www.ville-ideale.fr/palmares.php |
| Scraper open-source (TypeScript) | https://github.com/glarivie/ville-ideale-open-api |
