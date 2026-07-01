"""Validation du CSV qualité de l'air avant chargement."""

import logging
from pathlib import Path

import pandas as pd

from src.sources.qualite_air.config import OUTPUT_COLUMNS, RAW_DIR, RAW_FILE

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR) -> None:
    path = raw_dir / RAW_FILE
    if not path.exists():
        raise FileNotFoundError(f"[QualiteAir] Fichier manquant : {path}")

    df = pd.read_csv(path, nrows=5, dtype={"code_commune": str})
    missing = set(OUTPUT_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"[QualiteAir] Colonnes manquantes : {missing}")

    logger.info(f"[QualiteAir] Fichier OK : {path}")
