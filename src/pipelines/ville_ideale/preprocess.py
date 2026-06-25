"""Stage 2/4 — preprocess: clean and reshape the raw scrape (no DB, no enrichment).

Reads the raw JSON Lines from the download stage and produces one record per commune:

    data/raw/ville_ideale/{cities,reviews}.jsonl
        -> data/processed/ville_ideale/communes.jsonl

For each commune it:
  - de-duplicates reviews on ``review_id``;
  - groups the reviews under their commune and drops the per-review fields that are
    redundant once nested (code_commune, nom_ville, date_scraping);
  - keeps the aggregated rating fields from the city summary.

No database access and no NLP here — those belong to the load and process stages.

Usage:
    python -m src.pipelines.ville_ideale.preprocess
"""

import argparse
import logging

from src.pipelines.ville_ideale.io_utils import (
    PREPROCESSED,
    RAW_CITIES,
    RAW_REVIEWS,
    read_jsonl,
    write_jsonl,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Per-review fields kept in the nested ``avis`` array (redundant ones are dropped).
REVIEW_FIELDS = (
    "review_id",
    "pseudonyme",
    "date_avis",
    "note_moyenne",
    "notes",
    "points_positifs",
    "points_negatifs",
    "nb_accord",
    "nb_pas_accord",
)


def group_reviews(reviews: list[dict]) -> dict[str, list[dict]]:
    """Group reviews by commune, de-duplicating on ``review_id`` within each commune."""
    by_code: dict[str, list[dict]] = {}
    seen_ids: dict[str, set] = {}
    for r in reviews:
        code = r.get("code_commune")
        rid = r.get("review_id")
        ids = seen_ids.setdefault(code, set())
        if rid is not None and rid in ids:
            continue
        if rid is not None:
            ids.add(rid)
        by_code.setdefault(code, []).append({k: r.get(k) for k in REVIEW_FIELDS})
    return by_code


def build_records(cities: list[dict], reviews: list[dict]) -> list[dict]:
    """Merge city summaries and their reviews into one clean record per commune."""
    by_code = group_reviews(reviews)
    records = []
    for c in cities:
        code = c.get("code_commune")
        avis = by_code.get(code, [])
        records.append(
            {
                "code_commune": code,
                "nom_ville": c.get("nom_ville"),
                "note_globale": c.get("note_globale"),
                "nb_avis": len(avis),
                "notes": c.get("notes"),
                "avis": avis,
                "rang": c.get("rang"),
                "avis_complets": c.get("avis_complets"),
                "date_scraping": c.get("date_scraping"),
            }
        )
    return records


def run() -> None:
    cities = read_jsonl(RAW_CITIES)
    reviews = read_jsonl(RAW_REVIEWS)
    if not cities:
        logger.warning("No raw cities found in %s — nothing to preprocess", RAW_CITIES)
        return
    records = build_records(cities, reviews)
    write_jsonl(PREPROCESSED, records)
    logger.info("Preprocessed %d communes (%d reviews) -> %s", len(records), len(reviews), PREPROCESSED)


def main() -> None:
    argparse.ArgumentParser(description="Preprocess raw ville-ideale scrape into per-commune records.").parse_args()
    run()


if __name__ == "__main__":
    main()
