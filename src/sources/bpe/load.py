"""Chargement des stats BPE (Parquet) vers PostgreSQL."""

import logging
from pathlib import Path

import pandas as pd
from psycopg2.extras import execute_values

from src.sources.bpe.config import OUTPUT_COLUMNS, PROCESSED_DIR

logger = logging.getLogger(__name__)


def run(conn, processed_dir: Path = PROCESSED_DIR) -> None:
    """Charge le Parquet BPE commune_stats en base via UPSERT."""
    parquet_dir = processed_dir / "commune_stats"
    if not parquet_dir.exists():
        raise FileNotFoundError(f"Parquet BPE absent : {parquet_dir}. Lancer process() d'abord.")

    df = pd.read_parquet(parquet_dir)
    logger.info(f"[BPE Load] {len(df):,} communes lues")

    # Filtrer sur les communes existantes en base (évite FK violation)
    with conn.cursor() as cur:
        cur.execute("SELECT code_commune FROM communes")
        valid_codes = {row[0] for row in cur.fetchall()}
    before = len(df)
    df = df[df["code_commune"].isin(valid_codes)]
    if before - len(df):
        logger.info(f"[BPE Load] {before - len(df):,} communes ignorées (absentes de communes)")
    logger.info(f"[BPE Load] {len(df):,} communes à charger")

    cols = [c for c in OUTPUT_COLUMNS if c in df.columns]
    for col in cols[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    upsert_sql = f"""
        INSERT INTO bpe_commune_stats ({", ".join(cols)})
        VALUES %s
        ON CONFLICT (code_commune) DO UPDATE SET
            {", ".join(f"{c} = EXCLUDED.{c}" for c in cols[1:])}
    """

    rows = [
        tuple(None if pd.isna(row[c]) else (int(row[c]) if c != "code_commune" else row[c]) for c in cols)
        for _, row in df[cols].iterrows()
    ]

    batch_size = 10_000
    total = 0
    with conn.cursor() as cur:
        for start in range(0, len(rows), batch_size):
            execute_values(cur, upsert_sql, rows[start:start + batch_size])
            total += min(batch_size, len(rows) - start)
        conn.commit()

    logger.info(f"[BPE Load] {total:,} communes chargées (UPSERT)")
