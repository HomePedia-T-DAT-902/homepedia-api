"""Validation du fichier IVAL avant traitement Spark."""

import logging
from pathlib import Path

from src.sources.education.config import (
    IVAL_CODE_COL,
    IVAL_FILE,
    IVAL_PRESENTS_COL,
    IVAL_TAUX_COL,
    IVAL_YEAR_COL,
    RAW_DIR,
)

logger = logging.getLogger(__name__)

REQUIRED_COLS = {IVAL_CODE_COL, IVAL_YEAR_COL, IVAL_PRESENTS_COL, IVAL_TAUX_COL}


def run(raw_dir: Path = RAW_DIR) -> None:
    path = raw_dir / IVAL_FILE

    if not path.exists():
        raise FileNotFoundError(f"[Education] Fichier manquant : {path}")

    size_mb = path.stat().st_size / 1e6
    if size_mb < 0.1:
        raise ValueError(f"[Education] Fichier trop petit ({size_mb:.2f} MB)")

    import pandas as pd

    df = pd.read_csv(path, sep=";", nrows=5, encoding="utf-8", on_bad_lines="skip")
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"[Education] Colonnes manquantes : {missing}")

    logger.info(f"[Education] Fichier IVAL OK — {size_mb:.1f} MB")
