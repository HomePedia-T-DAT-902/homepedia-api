"""Validation et nettoyage du fichier BPE brut avant le job Spark."""

import logging
from pathlib import Path

import pandas as pd

from src.sources.bpe.config import CSV_FILE, RAW_DIR

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"depcom", "typequ"}
NULL_THRESHOLD = 0.10  # max 10% de nulls tolérés sur les colonnes clés


def run(raw_dir: Path = RAW_DIR) -> None:
    """
    Valide le fichier BPE brut. Lève une ValueError si la donnée n'est pas exploitable.
    Vérifie : présence du fichier, colonnes, taille, nulls excessifs.
    """
    csv_path = raw_dir / CSV_FILE
    logger.info(f"[BPE Preprocess] Validation de {csv_path}")

    _check_file_exists(csv_path)
    df = _load_sample(csv_path)
    _check_columns(df)
    _check_row_count(csv_path)
    _check_nulls(df)

    logger.info("[BPE Preprocess] Validation OK")


def _check_file_exists(path: Path) -> None:
    if not path.exists():
        raise ValueError(f"Fichier BPE absent : {path}. Lancer download() d'abord.")
    if path.stat().st_size < 1_000_000:
        raise ValueError(f"Fichier BPE trop petit ({path.stat().st_size} octets) — téléchargement incomplet ?")


def _load_sample(path: Path) -> pd.DataFrame:
    """Charge les 10 000 premières lignes pour validation rapide."""
    try:
        return pd.read_csv(path, sep=";", nrows=10_000, dtype=str)
    except Exception as e:
        raise ValueError(f"Impossible de lire le CSV BPE : {e}") from e


def _check_columns(df: pd.DataFrame) -> None:
    cols_lower = {c.lower() for c in df.columns}
    missing = REQUIRED_COLUMNS - cols_lower
    if missing:
        raise ValueError(
            f"Colonnes manquantes dans BPE : {missing}. "
            f"Colonnes détectées : {list(df.columns)}"
        )
    logger.info(f"[BPE Preprocess] Colonnes OK : {list(df.columns)}")


def _check_row_count(path: Path) -> None:
    # Estimation rapide via la taille du fichier (évite de lire 2.8M lignes)
    size_mb = path.stat().st_size / 1e6
    if size_mb < 50:
        raise ValueError(
            f"BPE trop petit ({size_mb:.0f} MB) — fichier potentiellement tronqué."
        )
    logger.info(f"[BPE Preprocess] Taille OK : {size_mb:.0f} MB")


def _check_nulls(df: pd.DataFrame) -> None:
    cols_lower = {c.lower(): c for c in df.columns}
    for col_lower in REQUIRED_COLUMNS:
        col = cols_lower.get(col_lower, col_lower)
        if col not in df.columns:
            continue
        null_rate = df[col].isna().mean()
        if null_rate > NULL_THRESHOLD:
            raise ValueError(
                f"Colonne '{col}' : {null_rate:.1%} de nulls (seuil : {NULL_THRESHOLD:.0%}). "
                "Données corrompues ?"
            )
    logger.info("[BPE Preprocess] Taux de nulls OK")
