"""
Load IRIS boundaries into PostgreSQL/PostGIS.

Reads the GeoJSON file downloaded by download_iris.py (via IGN WFS)
and loads it into the `iris_quartiers` table.

The dataset is ~49k features — small enough for direct loading without Spark.

GeoJSON properties (from IGN WFS):
    code_iris   VARCHAR(9)  — code_commune (5) + IRIS number (4)
    code_insee  VARCHAR(5)  — commune INSEE code
    nom_iris    VARCHAR     — IRIS name
    type_iris   CHAR(1)     — H=habitat, A=activity, D=misc, Z=undivided

Usage:
    python -m src.database.load_iris                     # load all IRIS
    python -m src.database.load_iris --truncate          # truncate before loading
"""

import argparse
import csv
import io
import json
import logging
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/iris")
GEOJSON_FILE = "contours-iris.geojson"

BATCH_SIZE = 5_000

CREATE_TMP_SQL = """
    CREATE TEMP TABLE IF NOT EXISTS tmp_iris (
        code_iris    VARCHAR(9),
        code_commune VARCHAR(5),
        nom_iris     VARCHAR(255),
        type_iris    CHAR(1),
        geom_json    TEXT
    )
"""

TMP_COPY_SQL = """
    COPY tmp_iris (code_iris, code_commune, nom_iris, type_iris, geom_json)
    FROM STDIN WITH (FORMAT CSV, NULL '\\N')
"""

INSERT_FROM_TMP_SQL = """
    INSERT INTO iris_quartiers (code_iris, code_commune, nom_iris, type_iris, geom)
    SELECT
        t.code_iris,
        t.code_commune,
        t.nom_iris,
        t.type_iris,
        ST_SetSRID(ST_Multi(ST_GeomFromGeoJSON(t.geom_json)), 4326)
    FROM tmp_iris t
    WHERE EXISTS (SELECT 1 FROM communes c WHERE c.code_commune = t.code_commune)
    ON CONFLICT (code_iris) DO UPDATE SET
        code_commune = EXCLUDED.code_commune,
        nom_iris     = EXCLUDED.nom_iris,
        type_iris    = EXCLUDED.type_iris,
        geom         = EXCLUDED.geom
"""


def get_connection():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ.get("POSTGRES_DB", "homepedia"),
        user=os.environ.get("POSTGRES_USER", "homepedia"),
        password=os.environ.get("POSTGRES_PASSWORD", "homepedia_secret"),
    )


def _v(val) -> str:
    """Convert a value to CSV string — null marker if None/empty."""
    if val is None or val == "":
        return "\\N"
    return str(val)


def _build_csv_buffer(batch: list[dict]) -> io.StringIO:
    """Build a CSV buffer from a batch of GeoJSON features."""
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    for feature in batch:
        props = feature.get("properties", {})
        geom = feature.get("geometry")
        if not geom:
            continue
        writer.writerow(
            [
                _v(props.get("code_iris")),
                _v(props.get("code_insee")),
                _v(props.get("nom_iris")),
                _v(props.get("type_iris")),
                json.dumps(geom),
            ]
        )
    buf.seek(0)
    return buf


def _flush_batch(cur, batch: list[dict]) -> int:
    """Copy a batch into tmp_iris then upsert into iris_quartiers. Returns inserted count."""
    buf = _build_csv_buffer(batch)
    cur.execute("TRUNCATE tmp_iris")
    cur.copy_expert(TMP_COPY_SQL, buf)
    cur.execute(INSERT_FROM_TMP_SQL)
    return cur.rowcount


def load_iris(truncate: bool = False) -> None:
    """Load IRIS boundaries from GeoJSON into PostgreSQL."""
    geojson_path = RAW_DIR / GEOJSON_FILE
    if not geojson_path.exists():
        logger.error(f"GeoJSON not found: {geojson_path}")
        logger.error("Run: python -m src.ingestion.download_iris")
        return

    logger.info(f"Reading: {geojson_path}  ({geojson_path.stat().st_size / 1e6:.1f} MB)")
    with open(geojson_path, encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    logger.info(f"Features to load: {len(features):,}")

    conn = get_connection()
    try:
        if truncate:
            logger.warning("TRUNCATE iris_quartiers")
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE iris_quartiers")
            conn.commit()

        with conn.cursor() as cur:
            cur.execute(CREATE_TMP_SQL)
        conn.commit()

        inserted = 0
        processed = 0

        for i in range(0, len(features), BATCH_SIZE):
            batch = features[i : i + BATCH_SIZE]
            with conn.cursor() as cur:
                inserted += _flush_batch(cur, batch)
            conn.commit()
            processed += len(batch)
            logger.info(f"  {processed:,} / {len(features):,} processed ({inserted:,} inserted)...")

        skipped = processed - inserted
        logger.info(f"=== Done — {inserted:,} IRIS loaded, {skipped:,} skipped (missing commune) ===")

    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load IGN Contours IRIS into PostgreSQL/PostGIS.")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate table before loading (default: upsert).",
    )
    args = parser.parse_args()

    load_iris(truncate=args.truncate)


if __name__ == "__main__":
    main()
