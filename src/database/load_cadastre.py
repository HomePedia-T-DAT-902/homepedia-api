"""
Chargement des parcelles cadastrales en base PostgreSQL/PostGIS.

Charge les fichiers GeoJSON.gz produits par download_cadastre.py
directement dans la table `parcelles_cadastrales` via COPY FROM STDIN.

Stratégie streaming : les fichiers GeoJSON sont parsés feature par feature
via ijson (si installé) pour éviter tout chargement mémoire complet.
Les features sont insérées par batch de BATCH_SIZE via une table temporaire.

Usage :
    python -m src.database.load_cadastre                    # tous les fichiers présents
    python -m src.database.load_cadastre --dept 75          # Paris uniquement
    python -m src.database.load_cadastre --dept 75 13 69    # Paris, BdR, Rhône
    python -m src.database.load_cadastre --truncate         # vide la table avant chargement
"""

import argparse
import csv
import decimal
import gzip
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

RAW_DIR = Path("data/raw/cadastre")

BATCH_SIZE = 50_000  # features par transaction

CREATE_TMP_SQL = """
    CREATE TEMP TABLE IF NOT EXISTS tmp_cadastre (
        id          VARCHAR(20),
        code_commune VARCHAR(5),
        prefixe     VARCHAR(3),
        section     VARCHAR(2),
        numero      VARCHAR(4),
        contenance  INTEGER,
        created     DATE,
        updated     DATE,
        geom_json   TEXT
    )
"""

TMP_COPY_SQL = """
    COPY tmp_cadastre (id, code_commune, prefixe, section, numero, contenance, created, updated, geom_json)
    FROM STDIN WITH (FORMAT CSV, NULL '\\N')
"""

INSERT_FROM_TMP_SQL = """
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


# ── Connexion ─────────────────────────────────────────────────────────────────


def get_connection():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ.get("POSTGRES_DB", "homepedia"),
        user=os.environ.get("POSTGRES_USER", "homepedia"),
        password=os.environ.get("POSTGRES_PASSWORD", "homepedia_secret"),
    )


# ── Parsing GeoJSON ───────────────────────────────────────────────────────────


def _v(val) -> str:
    """Convertit une valeur en chaîne CSV — null si None/vide."""
    if val is None or val == "":
        return "\\N"
    return str(val)


def iter_features(gz_path: Path):
    """
    Génère les features GeoJSON une par une depuis un fichier .geojson.gz.

    Utilise ijson pour un parsing streaming (O(1) mémoire) si disponible,
    sinon bascule sur json.load standard (chargement complet en mémoire).
    """
    with gzip.open(gz_path, "rt", encoding="utf-8") as f:
        try:
            import ijson

            yield from ijson.items(f, "features.item")
        except ImportError:
            logger.warning("ijson non installé — chargement complet en mémoire (risque OOM sur gros depts)")
            data = json.load(f)
            yield from data.get("features", [])


def _build_csv_buffer(batch: list) -> io.StringIO:
    """Construit un buffer CSV à partir d'un batch de features GeoJSON."""
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


# ── Chargement ────────────────────────────────────────────────────────────────


def _flush_batch(cur, batch: list) -> int:
    """Copie un batch dans tmp_cadastre puis l'insère dans la table cible."""
    buf = _build_csv_buffer(batch)
    cur.execute("TRUNCATE tmp_cadastre")
    cur.copy_expert(TMP_COPY_SQL, buf)
    cur.execute(INSERT_FROM_TMP_SQL)
    return len(batch)


def load_dept(conn, gz_path: Path) -> int:
    """
    Charge les parcelles d'un fichier GeoJSON.gz en base.
    Traitement par batch de BATCH_SIZE features — mémoire bornée.
    Retourne le nombre de parcelles chargées.
    """
    dept = gz_path.stem.replace("parcelles_", "")
    logger.info(f"  [{dept}] Lecture {gz_path.name}  ({gz_path.stat().st_size / 1e6:.0f} MB gz)")

    with conn.cursor() as cur:
        cur.execute(CREATE_TMP_SQL)
    conn.commit()

    total = 0
    batch: list = []

    for feature in iter_features(gz_path):
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

    logger.info(f"  [{dept}] {total:,} parcelles chargées au total")
    return total


def load_all(depts_filter: list[str] | None, truncate: bool) -> None:
    conn = get_connection()
    try:
        if truncate:
            logger.warning("TRUNCATE parcelles_cadastrales — toutes les parcelles existantes seront supprimées")
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE parcelles_cadastrales")
            conn.commit()

        gz_files = sorted(RAW_DIR.glob("parcelles_*.geojson.gz"))
        if not gz_files:
            logger.error(f"Aucun fichier GeoJSON.gz trouvé dans {RAW_DIR}")
            return

        if depts_filter:
            gz_files = [f for f in gz_files if any(f.name == f"parcelles_{d}.geojson.gz" for d in depts_filter)]

        logger.info(f"=== Chargement cadastre — {len(gz_files)} département(s) ===")

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

        logger.info("=== Chargement cadastre terminé ===")
        logger.info(f"  {total:,} parcelles chargées au total")
        if errors:
            logger.warning(f"  Départements en erreur : {errors}")

    finally:
        conn.close()


# ── Entrée ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Chargement des parcelles cadastrales en base PostgreSQL.")
    parser.add_argument(
        "--dept",
        nargs="+",
        metavar="DEPT",
        help="Code(s) département à charger (ex: 75 13). Défaut : tous les fichiers présents.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Vide la table avant chargement (TRUNCATE). Défaut : UPSERT incrémental.",
    )
    args = parser.parse_args()

    load_all(args.dept, args.truncate)


if __name__ == "__main__":
    main()
