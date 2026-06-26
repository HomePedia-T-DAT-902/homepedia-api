"""Chargement des données de délinquance vers PostgreSQL."""

import logging
from pathlib import Path

import pandas as pd

from src.sources.crime.config import PROCESSED_DIR

logger = logging.getLogger(__name__)

BATCH_SIZE = 50_000

COLUMNS = [
    "code_commune",
    "annee",
    "cambriolages_nombre",
    "cambriolages_pour_mille",
    "violences_nombre",
    "violences_pour_mille",
    "vols_nombre",
    "vols_pour_mille",
    "stups_nombre",
    "stups_pour_mille",
    "destructions_nombre",
    "destructions_pour_mille",
]


def run(conn, processed_dir: Path = PROCESSED_DIR) -> None:
    parquet_dir = processed_dir / "securite"
    if not parquet_dir.exists():
        raise FileNotFoundError(f"[Crime] Parquet manquant : {parquet_dir}")

    df = pd.read_parquet(parquet_dir)
    df = df[COLUMNS].dropna(subset=["code_commune", "annee"])
    df["annee"] = df["annee"].astype(int)

    # Filtrer les communes absentes de la table communes (géographie différente)
    with conn.cursor() as cur:
        cur.execute("SELECT code_commune FROM communes")
        communes_valides = {row[0] for row in cur.fetchall()}
    avant = len(df)
    df = df[df["code_commune"].isin(communes_valides)]
    logger.info(f"[Crime] {avant - len(df):,} lignes ignorées (commune inconnue), {len(df):,} à charger")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE securite_commune")
    conn.commit()

    for i in range(0, len(df), BATCH_SIZE):
        batch = df.iloc[i : i + BATCH_SIZE]
        _insert_batch(conn, batch)
        logger.info(f"[Crime] {min(i + BATCH_SIZE, len(df)):,}/{len(df):,} lignes chargées")

    logger.info("[Crime] Chargement terminé.")


def _insert_batch(conn, batch: pd.DataFrame) -> None:
    rows = [
        (
            row.code_commune,
            row.annee,
            _int(row.cambriolages_nombre),
            _float(row.cambriolages_pour_mille),
            _int(row.violences_nombre),
            _float(row.violences_pour_mille),
            _int(row.vols_nombre),
            _float(row.vols_pour_mille),
            _int(row.stups_nombre),
            _float(row.stups_pour_mille),
            _int(row.destructions_nombre),
            _float(row.destructions_pour_mille),
        )
        for row in batch.itertuples()
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO securite_commune (
                code_commune, annee,
                cambriolages_nombre, cambriolages_pour_mille,
                violences_nombre,    violences_pour_mille,
                vols_nombre,         vols_pour_mille,
                stups_nombre,        stups_pour_mille,
                destructions_nombre, destructions_pour_mille
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (code_commune, annee) DO UPDATE SET
                cambriolages_nombre     = EXCLUDED.cambriolages_nombre,
                cambriolages_pour_mille = EXCLUDED.cambriolages_pour_mille,
                violences_nombre        = EXCLUDED.violences_nombre,
                violences_pour_mille    = EXCLUDED.violences_pour_mille,
                vols_nombre             = EXCLUDED.vols_nombre,
                vols_pour_mille         = EXCLUDED.vols_pour_mille,
                stups_nombre            = EXCLUDED.stups_nombre,
                stups_pour_mille        = EXCLUDED.stups_pour_mille,
                destructions_nombre     = EXCLUDED.destructions_nombre,
                destructions_pour_mille = EXCLUDED.destructions_pour_mille
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
        return None if f != f else f  # NaN check
    except (TypeError, ValueError):
        return None
