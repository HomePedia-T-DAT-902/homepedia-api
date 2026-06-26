"""Validation du fichier délinquance avant traitement Spark."""

import logging
from pathlib import Path

from src.sources.crime.config import CODGEO_COL, RAW_DIR, RAW_FILE

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {CODGEO_COL, "annee", "indicateur", "taux_pour_mille", "est_diffuse"}
MIN_SIZE_MB = 10


def run(raw_dir: Path = RAW_DIR) -> None:
    path = raw_dir / RAW_FILE
    if not path.exists():
        raise FileNotFoundError(f"[Crime] Fichier manquant : {path}")

    size_mb = path.stat().st_size / 1e6
    if size_mb < MIN_SIZE_MB:
        raise ValueError(f"[Crime] Fichier trop petit ({size_mb:.0f} MB) — potentiellement tronqué.")
    logger.info(f"[Crime] Taille OK : {size_mb:.0f} MB")

    _check_columns(path)


def _check_columns(path: Path) -> None:
    try:
        import pandas as pd

        df = pd.read_parquet(path, columns=list(REQUIRED_COLUMNS))
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"[Crime] Colonnes manquantes : {missing}")
        logger.info(f"[Crime] Colonnes OK : {list(df.columns)}")
    except ImportError:
        logger.warning("[Crime] pandas non disponible — validation colonnes ignorée.")
