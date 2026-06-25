"""Chargement des contours IRIS vers PostgreSQL/PostGIS."""

import csv
import io
import json
import logging
from pathlib import Path

from src.sources.iris.config import BATCH_SIZE, DEST_FILE, RAW_DIR

logger = logging.getLogger(__name__)

_CREATE_TMP = """
    CREATE TEMP TABLE IF NOT EXISTS tmp_iris (
        code_iris    VARCHAR(9),
        code_commune VARCHAR(5),
        nom_iris     VARCHAR(255),
        type_iris    CHAR(1),
        geom_json    TEXT
    )
"""

_TMP_COPY = """
    COPY tmp_iris (code_iris, code_commune, nom_iris, type_iris, geom_json)
    FROM STDIN WITH (FORMAT CSV, NULL '\\N')
"""

_INSERT_FROM_TMP = """
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


def run(conn, raw_dir: Path = RAW_DIR) -> None:
    """Charge les ~49k contours IRIS en base via table temporaire + UPSERT."""
    geojson_path = raw_dir / DEST_FILE
    if not geojson_path.exists():
        raise FileNotFoundError(f"GeoJSON IRIS absent : {geojson_path}. Lancer download() d'abord.")

    logger.info(f"[IRIS Load] Lecture : {geojson_path}  ({geojson_path.stat().st_size / 1e6:.1f} MB)")
    with open(geojson_path, encoding="utf-8") as f:
        features = json.load(f).get("features", [])
    logger.info(f"[IRIS Load] {len(features):,} features à charger")

    with conn.cursor() as cur:
        cur.execute(_CREATE_TMP)
    conn.commit()

    inserted = processed = 0
    for i in range(0, len(features), BATCH_SIZE):
        batch = features[i:i + BATCH_SIZE]
        buf = _build_csv_buffer(batch)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE tmp_iris")
            cur.copy_expert(_TMP_COPY, buf)
            cur.execute(_INSERT_FROM_TMP)
            inserted += cur.rowcount
        conn.commit()
        processed += len(batch)
        logger.info(f"[IRIS Load] {processed:,} / {len(features):,} traités ({inserted:,} insérés)...")

    skipped = processed - inserted
    logger.info(f"[IRIS Load] {inserted:,} IRIS chargés, {skipped:,} ignorés (commune absente)")


def _build_csv_buffer(batch: list[dict]) -> io.StringIO:
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    for feature in batch:
        props = feature.get("properties", {})
        geom = feature.get("geometry")
        if not geom:
            continue
        writer.writerow([
            _v(props.get("code_iris")),
            _v(props.get("code_insee")),
            _v(props.get("nom_iris")),
            _v(props.get("type_iris")),
            json.dumps(geom),
        ])
    buf.seek(0)
    return buf


def _v(val) -> str:
    return "\\N" if (val is None or val == "") else str(val)
