"""Chargement de commune_risques vers PostgreSQL."""

import logging
from pathlib import Path

import pandas as pd

from src.sources.risques.config import PROCESSED_DIR
from src.sources.risques.process import BOOL_COLUMNS

logger = logging.getLogger(__name__)

COLUMNS = ["code_commune", *BOOL_COLUMNS]


def run(conn, processed_dir: Path = PROCESSED_DIR) -> None:
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
