# Homepedia API — Backlog

> État d'avancement (ce qui est fait) : [TASKS.md](../TASKS.md).
> Ce backlog liste le **travail restant** et les **idées** pour le repo `homepedia-api`.
> Les tâches frontend vivent dans le repo `homepedia-front`.

Légende priorité : P1 = important · P2 = secondaire · P3 = idée / bonus.

---

## Qualité & tests

| Priorité | Tâche |
|----------|-------|
| P1 | Étendre la couverture de tests API (geo, prix, risques, qualite-air, securite, education, equipements) |
| P1 | Test d'intégration du pipeline complet (raw → process → load → API) contre une base éphémère |
| P2 | Tests des étapes `preprocess` / `process` de chaque source (validation, agrégations Spark) |

---

## Pipeline & données

| Priorité | Tâche |
|----------|-------|
| P2 | Mise à jour incrémentale des sources (re-run ciblé sans tout retélécharger) |
| P2 | Documenter/mesurer les temps de traitement par source (DVF surtout) |
| P3 | Nouvelles sources potentielles (ex. loyers, revenus INSEE) — 1 dossier par source + entrée dans `SOURCES` |

> Ajouter une source = créer `src/sources/<nom>/` (interface `DataSource`) puis l'enregistrer
> dans le registre `SOURCES` de [`src/pipeline.py`](../src/pipeline.py). Voir [sources.md](sources.md).

---

## API

| Priorité | Tâche |
|----------|-------|
| P2 | Uniformiser les routers thématiques (aujourd'hui SQL direct) vers le pattern service/repository |
| P2 | Pagination sur les endpoints listes (`/risques`, `/prix/points`) |
| P3 | Cache applicatif des réponses lentes (aucun cache aujourd'hui) |

---

## Idées / bonus (P3)

| Tâche |
|-------|
| Déploiement en ligne (nécessite PostGIS) |
| NLP avancé sur les avis (sentiment) — aujourd'hui : word cloud stdlib uniquement |
| Documentation d'une architecture de scalabilité (orchestration type Airflow) pour la soutenance |
