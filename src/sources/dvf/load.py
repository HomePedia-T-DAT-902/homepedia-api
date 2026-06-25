"""Chargement des transactions DVF et calcul des price_trends vers PostgreSQL."""

import csv
import io
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from psycopg2.extras import execute_values

from src.sources.dvf.config import PROCESSED_DIR

logger = logging.getLogger(__name__)


def run(conn, processed_dir: Path = PROCESSED_DIR) -> None:
    """Charge les transactions DVF, puis calcule et charge les price_trends."""
    _load_transactions(conn, processed_dir)
    _compute_price_trends(conn, processed_dir)


def _load_transactions(conn, processed_dir: Path, batch_size: int = 100_000) -> None:
    if not processed_dir.exists():
        logger.warning(f"[DVF Load] Dossier absent : {processed_dir} — chargement ignoré")
        return

    df = _read_parquet(processed_dir)
    logger.info(f"[DVF Load] {len(df):,} transactions lues")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE dvf_transactions RESTART IDENTITY CASCADE")
    conn.commit()

    df = df.rename(columns={"nombre_pieces_principales": "nb_pieces"})
    columns = [
        "id_mutation",
        "code_commune",
        "date_mutation",
        "nature_mutation",
        "type_local",
        "valeur_fonciere",
        "surface_reelle_bati",
        "nb_pieces",
        "surface_terrain",
        "prix_m2",
        "longitude",
        "latitude",
    ]
    df["nb_pieces"] = pd.to_numeric(df["nb_pieces"], errors="coerce").round().astype("Int64")
    df["date_mutation"] = pd.to_datetime(df["date_mutation"]).dt.strftime("%Y-%m-%d")

    total = 0
    for start in range(0, len(df), batch_size):
        batch = df.iloc[start : start + batch_size]
        _copy_to_table(conn, batch, "dvf_transactions", columns)
        total += len(batch)
        logger.info(f"[DVF Load] {total:,} / {len(df):,} lignes chargées")

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE dvf_transactions
            SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
            WHERE longitude IS NOT NULL AND latitude IS NOT NULL
        """)
    conn.commit()
    logger.info(f"[DVF Load] {total:,} transactions chargées + géométries mises à jour")


def _compute_price_trends(conn, processed_dir: Path) -> None:
    if not processed_dir.exists():
        return

    df = _read_parquet(processed_dir)
    df = df[df["prix_m2"].notna() & df["date_mutation"].notna()].copy()
    df["date_mutation"] = pd.to_datetime(df["date_mutation"])
    df["annee"] = df["date_mutation"].dt.year.astype(int)
    df["trimestre"] = df["date_mutation"].dt.quarter.astype(int)

    trends = (
        df.groupby(["code_commune", "annee", "trimestre", "type_local"])
        .agg(prix_median_m2=("prix_m2", "median"), nb_transactions=("prix_m2", "count"))
        .reset_index()
    )
    trends["prix_median_m2"] = trends["prix_median_m2"].round(2)

    prev = trends.copy()
    prev["annee"] = prev["annee"] + 1
    prev = prev.rename(columns={"prix_median_m2": "prix_median_m2_prev"})
    trends = trends.merge(
        prev[["code_commune", "annee", "trimestre", "type_local", "prix_median_m2_prev"]],
        on=["code_commune", "annee", "trimestre", "type_local"],
        how="left",
    )
    trends["variation_annuelle_pct"] = (
        (trends["prix_median_m2"] - trends["prix_median_m2_prev"]) / trends["prix_median_m2_prev"] * 100
    ).round(2)
    trends = trends.drop(columns=["prix_median_m2_prev"])
    logger.info(f"[DVF Load] {len(trends):,} entrées price_trends calculées")

    upsert_sql = """
        INSERT INTO price_trends
            (code_commune, annee, trimestre, type_local, prix_median_m2, nb_transactions, variation_annuelle_pct)
        VALUES %s
        ON CONFLICT (code_commune, annee, trimestre, type_local) DO UPDATE SET
            prix_median_m2 = EXCLUDED.prix_median_m2,
            nb_transactions = EXCLUDED.nb_transactions,
            variation_annuelle_pct = EXCLUDED.variation_annuelle_pct
    """
    batch_size = 10_000
    total = 0
    with conn.cursor() as cur:
        for start in range(0, len(trends), batch_size):
            batch = trends.iloc[start : start + batch_size]
            rows = [
                (
                    row.code_commune,
                    int(row.annee),
                    int(row.trimestre),
                    row.type_local,
                    None if np.isnan(row.prix_median_m2) else float(row.prix_median_m2),
                    int(row.nb_transactions),
                    None if np.isnan(row.variation_annuelle_pct) else float(row.variation_annuelle_pct),
                )
                for row in batch.itertuples()
            ]
            execute_values(cur, upsert_sql, rows)
            total += len(batch)
    conn.commit()
    logger.info(f"[DVF Load] {total:,} entrées price_trends chargées (UPSERT)")


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
