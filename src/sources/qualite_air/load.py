"""Chargement de commune_qualite_air vers PostgreSQL."""

import logging
from pathlib import Path

import pandas as pd

from src.sources.qualite_air.config import OUTPUT_COLUMNS, PROCESSED_DIR

logger = logging.getLogger(__name__)


def run(conn, processed_dir: Path = PROCESSED_DIR) -> None:
    parquet_path = processed_dir / "qualite_air.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"[QualiteAir] Parquet manquant : {parquet_path}")

    df = pd.read_parquet(parquet_path)
    df = df.where(pd.notnull(df), None)

    with conn.cursor() as cur:
        cur.execute("SELECT code_commune FROM communes")
        communes_valides = {row[0] for row in cur.fetchall()}
    avant = len(df)
    df = df[df["code_commune"].isin(communes_valides)]
    logger.info(f"[QualiteAir] {avant - len(df):,} lignes ignorées (commune inconnue), {len(df):,} à charger")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE commune_qualite_air")
    conn.commit()

    rows = [tuple(row[col] for col in OUTPUT_COLUMNS) for _, row in df.iterrows()]
    placeholders = ", ".join(["%s"] * len(OUTPUT_COLUMNS))
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO commune_qualite_air ({', '.join(OUTPUT_COLUMNS)}) VALUES ({placeholders})",
            rows,
        )
    conn.commit()

    logger.info(f"[QualiteAir] {len(df):,} communes chargées dans commune_qualite_air")
