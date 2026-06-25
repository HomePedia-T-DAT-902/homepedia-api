"""Chargement des diagnostics DPE vers PostgreSQL."""

import csv
import io
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.sources.dpe.config import PROCESSED_DIR

logger = logging.getLogger(__name__)


def run(conn, processed_dir: Path = PROCESSED_DIR) -> None:
    """Charge les diagnostics DPE individuels via COPY FROM STDIN (~18M lignes)."""
    dpe_dir = processed_dir / "diagnostics"
    if not dpe_dir.exists():
        raise FileNotFoundError(f"Parquet DPE absent : {dpe_dir}. Lancer process() d'abord.")

    df = _read_parquet(dpe_dir)
    logger.info(f"[DPE Load] {len(df):,} diagnostics lus")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE dpe_diagnostics RESTART IDENTITY CASCADE")
    conn.commit()

    df["date_diagnostic"] = pd.to_datetime(df["date_diagnostic"]).dt.strftime("%Y-%m-%d")
    columns = ["code_commune", "date_diagnostic", "classe_energie", "consommation_moyenne", "source"]

    batch_size = 200_000
    total = 0
    for start in range(0, len(df), batch_size):
        batch = df.iloc[start:start + batch_size]
        _copy_to_table(conn, batch, "dpe_diagnostics", columns)
        total += len(batch)
        logger.info(f"[DPE Load] {total:,} / {len(df):,} diagnostics chargés")

    logger.info(f"[DPE Load] {total:,} diagnostics chargés")


def _read_parquet(parquet_dir: Path) -> pd.DataFrame:
    files = list(parquet_dir.glob("*.parquet"))
    if files:
        return pd.read_parquet(files[0])
    files = list(parquet_dir.glob("**/*.parquet"))
    if not files:
        raise FileNotFoundError(f"Aucun .parquet dans {parquet_dir}")
    return pd.read_parquet(parquet_dir)


def _copy_to_table(conn, df: pd.DataFrame, table: str, columns: list[str]) -> None:
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    for row in df[columns].itertuples(index=False):
        writer.writerow(["\\N" if (v is None or (isinstance(v, float) and np.isnan(v))) else v for v in row])
    buf.seek(0)
    with conn.cursor() as cur:
        cur.copy_expert(
            f"COPY {table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')",
            buf,
        )
    conn.commit()
