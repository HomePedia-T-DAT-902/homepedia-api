"""Chargement de commune_risques et risques_geopoints vers PostgreSQL."""

import logging
from pathlib import Path

import pandas as pd

from src.sources.risques.config import GEOPOINTS_FILE, PROCESSED_DIR, RAW_DIR
from src.sources.risques.process import BOOL_COLUMNS

logger = logging.getLogger(__name__)

COLUMNS = ["code_commune", *BOOL_COLUMNS]

# Risques zonaux : pas de geopoints API Géorisques → centroïde commune en fallback
_ZONE_RISKS = {"inondation", "seisme", "retrait_gonflement_argile", "radon", "feu_foret"}


def run(conn, processed_dir: Path = PROCESSED_DIR, raw_dir: Path = RAW_DIR) -> None:
    parquet_path = processed_dir / "risques.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"[Risques] Parquet manquant : {parquet_path}")

    df = pd.read_parquet(parquet_path)

    with conn.cursor() as cur:
        cur.execute("SELECT code_commune FROM communes")
        communes_valides = {row[0] for row in cur.fetchall()}
    avant = len(df)
    df = df[df["code_commune"].isin(communes_valides)]
    logger.info(f"[Risques] {avant - len(df):,} lignes ignorées (commune inconnue), {len(df):,} à charger")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE risques_geopoints")
        cur.execute("TRUNCATE TABLE commune_risques")
    conn.commit()

    rows = [tuple(row[col] for col in COLUMNS) for _, row in df.iterrows()]
    placeholders = ", ".join(["%s"] * len(COLUMNS))
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO commune_risques ({', '.join(COLUMNS)}) VALUES ({placeholders})",
            rows,
        )
    conn.commit()
    logger.info(f"[Risques] {len(df):,} communes chargées dans commune_risques")

    # --- Geopoints API Géorisques (MVT + ICPE) ---
    geopoints_path = raw_dir / GEOPOINTS_FILE
    if geopoints_path.exists():
        df_geo = pd.read_csv(geopoints_path, dtype={"code_commune": str})
        df_geo = df_geo[df_geo["code_commune"].isin(communes_valides)]
        df_geo = df_geo.dropna(subset=["longitude", "latitude"])
        api_rows = list(
            df_geo[["type_risque", "longitude", "latitude", "code_commune"]].itertuples(index=False, name=None)
        )
        if api_rows:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO risques_geopoints (type_risque, longitude, latitude, code_commune) "
                    "VALUES (%s, %s, %s, %s)",
                    api_rows,
                )
            conn.commit()
        logger.info(f"[Risques] {len(api_rows):,} geopoints API chargés dans risques_geopoints")
    else:
        logger.warning(f"[Risques] Fichier geopoints absent : {geopoints_path} — lancez d'abord download_geopoints")

    # --- Centroïdes communes pour les risques zonaux ---
    with conn.cursor() as cur:
        cur.execute(
            "SELECT code_commune, longitude, latitude FROM communes "
            "WHERE longitude IS NOT NULL AND latitude IS NOT NULL"
        )
        communes_coords = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

    centroid_rows = []
    for _, row in df.iterrows():
        code = row["code_commune"]
        coords = communes_coords.get(code)
        if not coords:
            continue
        lon, lat = coords
        for risk in _ZONE_RISKS:
            if row.get(risk):
                centroid_rows.append((risk, lon, lat, code))

    if centroid_rows:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO risques_geopoints (type_risque, longitude, latitude, code_commune) "
                "VALUES (%s, %s, %s, %s)",
                centroid_rows,
            )
        conn.commit()
    logger.info(f"[Risques] {len(centroid_rows):,} geopoints centroïdes chargés pour risques zonaux")
