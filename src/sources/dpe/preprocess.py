"""Validation des fichiers DPE bruts avant le job Spark."""

import logging
from pathlib import Path

import pandas as pd

from src.sources.dpe.config import DPE_ANCIEN_FILE, DPE_NOUVEAU_FILE, RAW_DIR

logger = logging.getLogger(__name__)

_REQUIRED_NOUVEAU = {"code_insee_ban", "etiquette_dpe"}
_REQUIRED_ANCIEN = {"classe_consommation_energie"}


def run(raw_dir: Path = RAW_DIR) -> None:
    """Vérifie que les fichiers DPE sont présents et lisibles."""
    nouveau = raw_dir / DPE_NOUVEAU_FILE
    ancien = raw_dir / DPE_ANCIEN_FILE

    if not nouveau.exists() and not ancien.exists():
        raise ValueError(f"Aucun fichier DPE dans {raw_dir}. Lancer download() d'abord.")

    if nouveau.exists():
        _check_csv(nouveau, _REQUIRED_NOUVEAU)
    else:
        logger.warning(f"[DPE Preprocess] {DPE_NOUVEAU_FILE} absent — uniquement DPE ancien")

    if ancien.exists():
        _check_csv(ancien, _REQUIRED_ANCIEN)
    else:
        logger.warning(f"[DPE Preprocess] {DPE_ANCIEN_FILE} absent — uniquement DPE nouveau")

    logger.info("[DPE Preprocess] Validation OK")


def _check_csv(path: Path, required_cols: set[str]) -> None:
    size_mb = path.stat().st_size / 1e6
    if size_mb < 1:
        raise ValueError(f"Fichier trop petit ({size_mb:.1f} MB) — téléchargement incomplet ? {path.name}")

    try:
        df = pd.read_csv(path, nrows=100, dtype=str)
    except Exception as e:
        raise ValueError(f"Impossible de lire {path.name} : {e}") from e

    cols_lower = {c.lower() for c in df.columns}
    missing = {c for c in required_cols if c.lower() not in cols_lower}
    if missing:
        raise ValueError(
            f"Colonnes manquantes dans {path.name} : {missing}. Colonnes détectées : {list(df.columns)[:10]}"
        )

    logger.info(f"[DPE Preprocess] {path.name} OK ({size_mb:.0f} MB, {len(df.columns)} colonnes)")
