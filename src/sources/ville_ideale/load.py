"""Stage 4/4 — load: upsert the enriched communes into PostgreSQL (city_reviews).

Reads the enriched records and writes them to the ``city_reviews`` table as JSONB:

    data/processed/ville_ideale/communes_enriched.jsonl  ->  PostgreSQL.city_reviews

It validates every ``code_commune`` against the ``communes`` reference table (the foreign
key) and drops/logs the ones that are absent (e.g. former, merged communes), then upserts.

This stage is self-contained: it owns its DB connection and the idempotent table DDL, so
the pipeline folder does not depend on the (separately refactored) database modules.

Usage:
    python -m src.sources.ville_ideale.load
"""

import logging
from pathlib import Path

from psycopg2.extras import Json, execute_values

from src.sources.ville_ideale import config
from src.sources.ville_ideale.io_utils import read_jsonl

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Owned by this data type: created on demand so the pipeline is self-contained.
CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS city_reviews (
        code_commune   VARCHAR(5) PRIMARY KEY REFERENCES communes(code_commune),
        note_globale   FLOAT,
        nb_avis        INTEGER,
        notes          JSONB,
        avis           JSONB,
        word_cloud     JSONB,
        rang           VARCHAR(20),
        avis_complets  BOOLEAN,
        date_scraping  DATE
    );
    ALTER TABLE city_reviews ADD COLUMN IF NOT EXISTS word_cloud JSONB;
    CREATE INDEX IF NOT EXISTS idx_city_reviews_notes ON city_reviews USING GIN (notes);
    CREATE INDEX IF NOT EXISTS idx_city_reviews_avis ON city_reviews USING GIN (avis);
    CREATE INDEX IF NOT EXISTS idx_city_reviews_note_globale ON city_reviews (note_globale);
"""

UPSERT_SQL = """
    INSERT INTO city_reviews
        (code_commune, note_globale, nb_avis, notes, avis, word_cloud, rang, avis_complets, date_scraping)
    VALUES %s
    ON CONFLICT (code_commune) DO UPDATE SET
        note_globale = EXCLUDED.note_globale,
        nb_avis = EXCLUDED.nb_avis,
        notes = EXCLUDED.notes,
        avis = EXCLUDED.avis,
        word_cloud = EXCLUDED.word_cloud,
        rang = EXCLUDED.rang,
        avis_complets = EXCLUDED.avis_complets,
        date_scraping = EXCLUDED.date_scraping
"""


def filter_known_communes(records: list[dict], valid_codes: set[str]):
    """Keep only records whose commune exists in the reference table (FK guard).

    Returns:
        ``(kept, dropped)`` where dropped is the list of unknown ``code_commune`` values.
    """
    kept, dropped = [], []
    for r in records:
        (kept if r.get("code_commune") in valid_codes else dropped).append(r)
    dropped_codes = [r.get("code_commune") for r in dropped]
    return kept, dropped_codes


def load(conn, records: list[dict]) -> int:
    """Create the table if needed, validate against communes, and upsert. Returns row count."""
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
        conn.commit()
        cur.execute("SELECT code_commune FROM communes")
        valid_codes = {row[0] for row in cur.fetchall()}

    if not valid_codes:
        logger.warning("Reference table communes is empty — load the communes first. Skipping.")
        return 0

    kept, dropped = filter_known_communes(records, valid_codes)
    logger.info("%d communes, %d valid, %d outside the communes reference", len(records), len(kept), len(dropped))
    if dropped:
        sample = sorted(set(dropped))
        logger.warning(
            "Skipped codes absent from communes (e.g. former communes): %s%s",
            sample[:10],
            "..." if len(sample) > 10 else "",
        )

    if not kept:
        return 0

    rows = [
        (
            r["code_commune"],
            r.get("note_globale"),
            r.get("nb_avis"),
            Json(r.get("notes")),
            Json(r.get("avis")),
            Json(r.get("word_cloud")),
            r.get("rang"),
            r.get("avis_complets"),
            r.get("date_scraping"),
        )
        for r in kept
    ]
    with conn.cursor() as cur:
        execute_values(cur, UPSERT_SQL, rows)
        conn.commit()
    logger.info("Upserted %d communes into city_reviews", len(rows))
    return len(rows)


def run(conn, processed_dir: Path = config.PROCESSED_DIR) -> None:
    enriched = processed_dir / config.ENRICHED_FILE
    records = read_jsonl(enriched)
    if not records:
        logger.warning("No enriched records in %s — run preprocess then process first", enriched)
        return
    load(conn, records)
