"""Chargement des données GEO (régions, départements, communes) vers PostgreSQL."""

import json
import logging
from pathlib import Path

import ijson
import pandas as pd

from src.sources.geo.config import PROCESSED_DIR, RAW_DIR

logger = logging.getLogger(__name__)

STREAMING_THRESHOLD_MB = 50
BATCH_SIZE = 500


def run(conn, raw_dir=RAW_DIR, processed_dir=PROCESSED_DIR) -> None:
    _load_regions(conn, processed_dir, raw_dir)
    _load_departements(conn, processed_dir, raw_dir)
    _load_communes(conn, processed_dir, raw_dir)


def _load_regions(conn, processed_dir, raw_dir) -> None:
    logger.info("[GEO Load] Chargement régions")
    df = pd.read_parquet(next((processed_dir / "regions").glob("*.parquet")))
    geoms = _read_geometries(raw_dir / "regions-5m.geojson")
    with conn.cursor() as cur:
        for _, row in df.iterrows():
            cur.execute(
                "INSERT INTO regions (code_region, nom, geom) VALUES (%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)) ON CONFLICT (code_region) DO UPDATE SET nom=EXCLUDED.nom, geom=EXCLUDED.geom",
                (row["code_region"], row["nom"], geoms.get(row["code_region"])),
            )
    conn.commit()
    logger.info(f"[GEO Load] {len(df)} régions chargées")


def _load_departements(conn, processed_dir, raw_dir) -> None:
    logger.info("[GEO Load] Chargement départements")
    df = pd.read_parquet(next((processed_dir / "departements").glob("*.parquet")))
    geoms = _read_geometries(raw_dir / "departements-5m.geojson")
    with conn.cursor() as cur:
        for _, row in df.iterrows():
            cur.execute(
                "INSERT INTO departements (code_departement, nom, code_region, geom) VALUES (%s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)) ON CONFLICT (code_departement) DO UPDATE SET nom=EXCLUDED.nom, code_region=EXCLUDED.code_region, geom=EXCLUDED.geom",
                (row["code_departement"], row["nom"], row["code_region"], geoms.get(row["code_departement"])),
            )
    conn.commit()
    logger.info(f"[GEO Load] {len(df)} départements chargés")


def _load_communes(conn, processed_dir, raw_dir) -> None:
    """Charge les communes par batch en streamant les géométries pour éviter les OOM."""
    logger.info("[GEO Load] Chargement communes (streaming batch)")
    df = pd.read_parquet(next((processed_dir / "communes").glob("*.parquet")))
    if "code_region" in df.columns:
        df["code_region"] = df["code_region"].astype(str).str.zfill(2)

    df_index = df.set_index("code_commune")
    for geojson_file, geom_col in [("communes-5m.geojson", "geom"), ("communes-50m.geojson", "geom_simplified")]:
        path = raw_dir / geojson_file
        logger.info(f"[GEO Load] Streaming {geojson_file} ({path.stat().st_size / 1e6:.0f} MB)")
        _stream_commune_geometries(conn, df_index, path, geom_col)

    logger.info("[GEO Load] Communes chargées")
    _load_arrondissements(conn, raw_dir)


def _stream_commune_geometries(conn, df_index, geojson_path, geom_col) -> None:
    batch, total = [], 0
    with open(geojson_path, "rb") as f:
        for feature in ijson.items(f, "features.item", use_float=True):
            code = feature["properties"]["code"]
            if code not in df_index.index:
                continue
            row = df_index.loc[code]
            geom = feature["geometry"]
            if geom["type"] == "Polygon":
                geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
            batch.append((code, row.get("nom"), row.get("code_departement"), row.get("code_region"),
                          row.get("code_postal"), _int(row.get("population")), _float(row.get("superficie")),
                          _float(row.get("densite")), _float(row.get("latitude")), _float(row.get("longitude")),
                          json.dumps(geom), geom_col))
            if len(batch) >= BATCH_SIZE:
                _upsert_communes_batch(conn, batch)
                total += len(batch)
                batch = []
    if batch:
        _upsert_communes_batch(conn, batch)
        total += len(batch)
    conn.commit()
    logger.info(f"[GEO Load] {total} géométries {geom_col} mises à jour")


def _upsert_communes_batch(conn, batch) -> None:
    with conn.cursor() as cur:
        for code, nom, dept, region, postal, pop, superficie, densite, lat, lon, geom_json, geom_col in batch:
            cur.execute(
                f"INSERT INTO communes (code_commune, nom, code_departement, code_region, code_postal, population, superficie, densite, latitude, longitude, {geom_col}) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, ST_SetSRID(ST_GeomFromGeoJSON(%s),4326)) ON CONFLICT (code_commune) DO UPDATE SET {geom_col}=EXCLUDED.{geom_col}, nom=EXCLUDED.nom, population=EXCLUDED.population",
                (code, nom, dept, region, postal, pop, superficie, densite, lat, lon, geom_json),
            )


def _load_arrondissements(conn, raw_dir) -> None:
    """Charge les arrondissements de Paris, Lyon, Marseille."""
    prefixes = ("751", "6938", "132")
    geoms_50m = _read_geometries(raw_dir / "communes-50m.geojson")
    loaded = 0
    with open(raw_dir / "communes-5m.geojson", "rb") as f:
        for feature in ijson.items(f, "features.item", use_float=True):
            code = feature["properties"]["code"]
            if not any(code.startswith(p) for p in prefixes):
                continue
            props = feature["properties"]
            geom = feature["geometry"]
            if geom["type"] == "Polygon":
                geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO communes (code_commune, nom, code_departement, code_region, geom, geom_simplified) VALUES (%s,%s,%s,%s, ST_SetSRID(ST_GeomFromGeoJSON(%s),4326), ST_SetSRID(ST_GeomFromGeoJSON(%s),4326)) ON CONFLICT (code_commune) DO UPDATE SET nom=EXCLUDED.nom, geom=EXCLUDED.geom",
                    (code, props["nom"], props.get("departement", code[:2]), props.get("region"), json.dumps(geom), geoms_50m.get(code)),
                )
            loaded += 1
    conn.commit()
    logger.info(f"[GEO Load] {loaded} arrondissements chargés")


def _read_geometries(path: Path) -> dict:
    size_mb = path.stat().st_size / 1e6
    if size_mb > STREAMING_THRESHOLD_MB:
        geoms = {}
        with open(path, "rb") as f:
            for feat in ijson.items(f, "features.item", use_float=True):
                code = feat["properties"]["code"]
                geom = feat["geometry"]
                if geom["type"] == "Polygon":
                    geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
                geoms[code] = json.dumps(geom)
        return geoms
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {feat["properties"]["code"]: json.dumps(feat["geometry"]) for feat in data["features"]}


def _int(v): return int(v) if v is not None and str(v) != "nan" else None
def _float(v): return float(v) if v is not None and str(v) != "nan" else None
