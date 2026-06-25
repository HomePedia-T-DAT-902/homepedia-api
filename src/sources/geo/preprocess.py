"""Validation des fichiers GEO bruts avant le job Spark."""

import logging

import pandas as pd

from src.sources.geo.config import (
    COMMUNES_CSV_FILE,
    COMMUNES_CSV_REQUIRED_COLS,
    POPULATION_FILE,
    RAW_DIR,
    REQUIRED_FILES,
)

logger = logging.getLogger(__name__)


def run(raw_dir=RAW_DIR) -> None:
    """Vérifie que tous les fichiers GEO sont présents et exploitables."""
    logger.info("[GEO Preprocess] Validation des fichiers bruts")
    _check_files_exist(raw_dir)
    _check_communes_csv(raw_dir)
    _check_population_xlsx(raw_dir)
    logger.info("[GEO Preprocess] Validation OK")


def _check_files_exist(raw_dir) -> None:
    missing = [f for f in REQUIRED_FILES if not (raw_dir / f).exists()]
    if missing:
        raise ValueError(f"Fichiers GEO manquants : {missing}. Lancer download() d'abord.")
    logger.info(f"[GEO Preprocess] {len(REQUIRED_FILES)} fichiers présents")


def _check_communes_csv(raw_dir) -> None:
    path = raw_dir / COMMUNES_CSV_FILE
    try:
        df = pd.read_csv(path, nrows=100, dtype=str)
    except Exception as e:
        raise ValueError(f"Impossible de lire {COMMUNES_CSV_FILE} : {e}") from e
    cols = {c.lower() for c in df.columns}
    missing = COMMUNES_CSV_REQUIRED_COLS - cols
    if missing:
        raise ValueError(f"Colonnes manquantes dans communes CSV : {missing}")
    logger.info("[GEO Preprocess] Colonnes communes CSV OK")


def _check_population_xlsx(raw_dir) -> None:
    path = raw_dir / POPULATION_FILE
    if path.stat().st_size < 100_000:
        raise ValueError(f"Fichier population trop petit ({path.stat().st_size} octets) — incomplet ?")
    try:
        pd.read_excel(path, nrows=5)
    except Exception as e:
        raise ValueError(f"Impossible de lire {POPULATION_FILE} : {e}") from e
    logger.info("[GEO Preprocess] Fichier population OK")
