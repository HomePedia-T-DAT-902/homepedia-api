"""Chargement des résultats bac vers PostgreSQL."""

import logging
from pathlib import Path

import pandas as pd

from src.sources.education.config import PROCESSED_DIR

logger = logging.getLogger(__name__)

BATCH_SIZE = 50_000
COLUMNS = ["code_commune", "annee", "bac_presents", "bac_taux_reussite"]


def run(conn, processed_dir: Path = PROCESSED_DIR) -> None:
    parquet_dir = processed_dir / "bac"
    if not parquet_dir.exists():
        raise FileNotFoundError(f"[Education] Parquet manquant : {parquet_dir}")

    df = pd.read_parquet(parquet_dir)
    df = df[COLUMNS].dropna(subset=["code_commune", "annee"])
    df["annee"] = df["annee"].astype(int)

    # Filtrer les communes absentes de la table communes
    with conn.cursor() as cur:
        cur.execute("SELECT code_commune FROM communes")
        communes_valides = {row[0] for row in cur.fetchall()}
    avant = len(df)
    df = df[df["code_commune"].isin(communes_valides)]
    logger.info(f"[Education] {avant - len(df):,} lignes ignorées (commune inconnue), {len(df):,} à charger")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE education_commune")
    conn.commit()

    for i in range(0, len(df), BATCH_SIZE):
        batch = df.iloc[i : i + BATCH_SIZE]
        _insert_batch(conn, batch)
        logger.info(f"[Education] {min(i + BATCH_SIZE, len(df)):,}/{len(df):,} lignes chargées")

    logger.info("[Education] Chargement terminé.")


def _insert_batch(conn, batch: pd.DataFrame) -> None:
    rows = [
        (
            row.code_commune,
            row.annee,
            _int(row.bac_presents),
            _float(row.bac_taux_reussite),
        )
        for row in batch.itertuples()
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO education_commune (code_commune, annee, bac_presents, bac_taux_reussite)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (code_commune, annee) DO UPDATE SET
                bac_presents      = EXCLUDED.bac_presents,
                bac_taux_reussite = EXCLUDED.bac_taux_reussite
            """,
            rows,
        )
    conn.commit()


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _float(v) -> float | None:
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None
