"""
Chargement des données géographiques (Parquet + GeoJSON) vers PostgreSQL/PostGIS.

Pipeline :
  1. Exécute le schéma SQL (CREATE TABLE IF NOT EXISTS)
  2. Charge les régions (Parquet attributs + GeoJSON géométries)
  3. Charge les départements (idem)
  4. Charge les communes (idem, avec geom_simplified depuis contours 50m)

Sources :
  - data/processed/geo/   → Parquet (attributs issus de spark_geo.py)
  - data/raw/geo/         → GeoJSON (géométries Etalab)

Usage :
    python -m src.database.postgres_loader
    python -m src.database.postgres_loader --processed-dir data/processed/geo --raw-dir data/raw/geo
"""

import argparse
import json
import logging
import os
from pathlib import Path

import pandas as pd
import psycopg2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "postgres_schema.sql"


def get_connection():
    """Crée une connexion PostgreSQL depuis les variables d'environnement."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ.get("POSTGRES_DB", "homepedia"),
        user=os.environ.get("POSTGRES_USER", "homepedia"),
        password=os.environ.get("POSTGRES_PASSWORD", "homepedia_secret"),
    )


def init_schema(conn) -> None:
    """Exécute le fichier SQL de création du schéma."""
    logger.info(f"Exécution du schéma : {SCHEMA_PATH}")
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.info("Schéma initialisé")


# ── Lecture des données ──────────────────────────────────────────────────────


def read_parquet_dir(parquet_dir: Path) -> pd.DataFrame:
    """Lit un dossier Parquet (écrit par Spark avec coalesce(1))."""
    files = list(parquet_dir.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"Aucun fichier .parquet dans {parquet_dir}")
    logger.info(f"Lecture Parquet : {files[0]}")
    return pd.read_parquet(files[0])


def read_geojson_geometries(geojson_path: Path) -> dict[str, str]:
    """
    Lit un GeoJSON et retourne un dict {code: geometry_json}.
    Le code est extrait depuis properties.code.
    """
    logger.info(f"Lecture géométries : {geojson_path}")
    with open(geojson_path, encoding="utf-8") as f:
        data = json.load(f)

    geometries = {}
    for feature in data["features"]:
        code = feature["properties"]["code"]
        geom = feature["geometry"]
        # Forcer en MultiPolygon pour cohérence avec le schéma
        if geom["type"] == "Polygon":
            geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
        geometries[code] = json.dumps(geom)

    logger.info(f"  → {len(geometries)} géométries extraites")
    return geometries


# ── Chargement ───────────────────────────────────────────────────────────────


def load_regions(conn, processed_dir: Path, raw_dir: Path) -> None:
    """Charge les régions (attributs + géométries)."""
    logger.info("=== Chargement régions ===")
    df = read_parquet_dir(processed_dir / "regions")
    geoms = read_geojson_geometries(raw_dir / "regions-5m.geojson")

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            code = row["code_region"]
            geom_json = geoms.get(code)
            cur.execute(
                """
                INSERT INTO regions (code_region, nom, geom)
                VALUES (%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                ON CONFLICT (code_region) DO UPDATE SET
                    nom = EXCLUDED.nom,
                    geom = EXCLUDED.geom
                """,
                (code, row["nom"], geom_json),
            )
    conn.commit()
    logger.info(f"  → {len(df)} régions chargées")


def load_departements(conn, processed_dir: Path, raw_dir: Path) -> None:
    """Charge les départements (attributs + géométries)."""
    logger.info("=== Chargement départements ===")
    df = read_parquet_dir(processed_dir / "departements")
    geoms = read_geojson_geometries(raw_dir / "departements-5m.geojson")

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            code = row["code_departement"]
            geom_json = geoms.get(code)
            cur.execute(
                """
                INSERT INTO departements (code_departement, nom, code_region, geom)
                VALUES (%s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                ON CONFLICT (code_departement) DO UPDATE SET
                    nom = EXCLUDED.nom,
                    code_region = EXCLUDED.code_region,
                    geom = EXCLUDED.geom
                """,
                (code, row["nom"], row["code_region"], geom_json),
            )
    conn.commit()
    logger.info(f"  → {len(df)} départements chargés")


def load_communes(conn, processed_dir: Path, raw_dir: Path) -> None:
    """
    Charge les communes (attributs Parquet + géométries GeoJSON).
    - geom : contours 5m (précis)
    - geom_simplified : contours 50m (carte zoomée)
    """
    logger.info("=== Chargement communes ===")
    df = read_parquet_dir(processed_dir / "communes")
    # Padder les codes région (ex: "1" → "01") pour correspondre à la table regions
    if "code_region" in df.columns:
        df["code_region"] = df["code_region"].astype(str).str.zfill(2)
    geoms_5m = read_geojson_geometries(raw_dir / "communes-5m.geojson")
    geoms_50m = read_geojson_geometries(raw_dir / "communes-50m.geojson")

    loaded = 0
    skipped = 0

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            code = row["code_commune"]
            geom_5m = geoms_5m.get(code)
            geom_50m = geoms_50m.get(code)

            if not geom_5m:
                skipped += 1
                continue

            cur.execute(
                """
                INSERT INTO communes (
                    code_commune, nom, code_departement, code_region,
                    code_postal, population, superficie, densite,
                    latitude, longitude, geom, geom_simplified
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
                )
                ON CONFLICT (code_commune) DO UPDATE SET
                    nom = EXCLUDED.nom,
                    code_departement = EXCLUDED.code_departement,
                    code_region = EXCLUDED.code_region,
                    code_postal = EXCLUDED.code_postal,
                    population = EXCLUDED.population,
                    superficie = EXCLUDED.superficie,
                    densite = EXCLUDED.densite,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    geom = EXCLUDED.geom,
                    geom_simplified = EXCLUDED.geom_simplified
                """,
                (
                    code,
                    row["nom"],
                    row.get("code_departement"),
                    row.get("code_region"),
                    row.get("code_postal"),
                    int(row["population"]) if pd.notna(row.get("population")) else None,
                    float(row["superficie"]) if pd.notna(row.get("superficie")) else None,
                    float(row["densite"]) if pd.notna(row.get("densite")) else None,
                    float(row["latitude"]) if pd.notna(row.get("latitude")) else None,
                    float(row["longitude"]) if pd.notna(row.get("longitude")) else None,
                    geom_5m,
                    geom_50m,
                ),
            )

            loaded += 1
            if loaded % 5000 == 0:
                conn.commit()
                logger.info(f"  → {loaded} communes chargées...")

    conn.commit()
    logger.info(f"  → {loaded} communes chargées, {skipped} ignorées (pas de géométrie)")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Chargement des données géographiques en base.")
    parser.add_argument("--processed-dir", default="data/processed/geo", help="Dossier Parquet.")
    parser.add_argument("--raw-dir", default="data/raw/geo", help="Dossier GeoJSON bruts.")
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir)
    raw_dir = Path(args.raw_dir)

    conn = get_connection()
    try:
        init_schema(conn)
        load_regions(conn, processed_dir, raw_dir)
        load_departements(conn, processed_dir, raw_dir)
        load_communes(conn, processed_dir, raw_dir)
        logger.info("=== Chargement terminé ===")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
