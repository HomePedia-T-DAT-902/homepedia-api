"""Chargement des parcelles cadastrales vers PostgreSQL/PostGIS."""

import csv
import decimal
import gzip
import io
import json
import logging
from pathlib import Path

from src.sources.cadastre.config import BATCH_SIZE, RAW_DIR

logger = logging.getLogger(__name__)

_CREATE_TMP = """
    CREATE TEMP TABLE IF NOT EXISTS tmp_cadastre (
        id           VARCHAR(20),
        code_commune VARCHAR(5),
        prefixe      VARCHAR(3),
        section      VARCHAR(2),
        numero       VARCHAR(4),
        contenance   INTEGER,
        created      DATE,
        updated      DATE,
        geom_json    TEXT
    )
"""

_TMP_COPY = """
    COPY tmp_cadastre (id, code_commune, prefixe, section, numero, contenance, created, updated, geom_json)
    FROM STDIN WITH (FORMAT CSV, NULL '\\N')
"""

_INSERT_FROM_TMP = """
    INSERT INTO parcelles_cadastrales
        (id, code_commune, prefixe, section, numero, contenance, created, updated, geom)
    SELECT
        id, code_commune, prefixe, section, numero,
        contenance::INTEGER,
        created::DATE,
        updated::DATE,
        ST_SetSRID(ST_GeomFromGeoJSON(geom_json), 4326)
    FROM tmp_cadastre
    ON CONFLICT (id) DO UPDATE SET
        code_commune = EXCLUDED.code_commune,
        contenance   = EXCLUDED.contenance,
        updated      = EXCLUDED.updated,
        geom         = EXCLUDED.geom
"""


def run(conn, raw_dir: Path = RAW_DIR, depts: list[str] | None = None, truncate: bool = False) -> None:
    """Charge les parcelles cadastrales depuis les GeoJSON.gz par département."""
    if truncate:
        logger.warning("[Cadastre Load] TRUNCATE parcelles_cadastrales")
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE parcelles_cadastrales")
        conn.commit()

    gz_files = sorted(raw_dir.glob("parcelles_*.geojson.gz"))
    if not gz_files:
        raise FileNotFoundError(f"Aucun fichier GeoJSON.gz dans {raw_dir}. Lancer download() d'abord.")

    if depts:
        gz_files = [f for f in gz_files if any(f.name == f"parcelles_{d}.geojson.gz" for d in depts)]

    logger.info(f"[Cadastre Load] {len(gz_files)} département(s) à charger")

    total = 0
    errors = []
    for i, gz_path in enumerate(gz_files, 1):
        dept = gz_path.stem.replace("parcelles_", "")
        logger.info(f"[{i}/{len(gz_files)}] Département {dept}")
        try:
            total += load_dept(conn, gz_path)
        except Exception as e:
            logger.error(f"  [{dept}] ERREUR : {e}")
            conn.rollback()
            errors.append(dept)

    logger.info(f"[Cadastre Load] {total:,} parcelles chargées au total")
    if errors:
        logger.warning(f"  Départements en erreur : {errors}")


def load_dept(conn, gz_path: Path) -> int:
    """Charge les parcelles d'un département. Retourne le nombre chargé."""
    dept = gz_path.stem.replace("parcelles_", "")
    logger.info(f"  [{dept}] {gz_path.name}  ({gz_path.stat().st_size / 1e6:.0f} MB gz)")

    with conn.cursor() as cur:
        cur.execute(_CREATE_TMP)
    conn.commit()

    total = 0
    batch: list = []

    for feature in _iter_features(gz_path):
        batch.append(feature)
        if len(batch) >= BATCH_SIZE:
            with conn.cursor() as cur:
                _flush_batch(cur, batch)
            conn.commit()
            total += len(batch)
            logger.info(f"  [{dept}] {total:,} parcelles chargées...")
            batch = []

    if batch:
        with conn.cursor() as cur:
            _flush_batch(cur, batch)
        conn.commit()
        total += len(batch)

    logger.info(f"  [{dept}] {total:,} parcelles au total")
    return total


def _iter_features(gz_path: Path):
    """Streaming ijson O(1) mémoire ; fallback json.load si ijson absent."""
    with gzip.open(gz_path, "rt", encoding="utf-8") as f:
        try:
            import ijson

            yield from ijson.items(f, "features.item")
        except ImportError:
            logger.warning("ijson non installé — chargement complet en mémoire")
            data = json.load(f)
            yield from data.get("features", [])


def _flush_batch(cur, batch: list) -> None:
    buf = _build_csv_buffer(batch)
    cur.execute("TRUNCATE tmp_cadastre")
    cur.copy_expert(_TMP_COPY, buf)
    cur.execute(_INSERT_FROM_TMP)


def _build_csv_buffer(batch: list) -> io.StringIO:
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    for feature in batch:
        props = feature.get("properties", {})
        geom = feature.get("geometry")
        if not geom:
            continue
        writer.writerow(
            [
                _v(props.get("id")),
                _v(props.get("commune")),
                _v(props.get("prefixe")),
                _v(props.get("section")),
                _v(props.get("numero")),
                _v(props.get("contenance")),
                _v(props.get("created")),
                _v(props.get("updated")),
                json.dumps(geom, default=lambda o: float(o) if isinstance(o, decimal.Decimal) else o),
            ]
        )
    buf.seek(0)
    return buf


def _v(val) -> str:
    return "\\N" if (val is None or val == "") else str(val)
