"""Validation des fichiers DVF bruts avant le job Spark."""

import logging
from pathlib import Path

import pandas as pd

from src.sources.dvf.config import RAW_DIR

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR) -> None:
    """Vérifie que les fichiers DVF sont présents et exploitables."""
    geo_dir = raw_dir / "geo"
    dgfip_dir = raw_dir / "dgfip"

    geo_files = sorted(geo_dir.glob("dvf_*.csv")) if geo_dir.exists() else []
    dgfip_files = sorted(dgfip_dir.glob("dvf_*.csv")) if dgfip_dir.exists() else []

    if not geo_files and not dgfip_files:
        raise ValueError(f"Aucun fichier DVF dans {raw_dir}. Lancer download() d'abord.")

    logger.info(f"[DVF Preprocess] {len(geo_files)} fichier(s) Geo-DVF, {len(dgfip_files)} fichier(s) DGFiP")

    for f in geo_files:
        _check_csv(f, sep=",", required_cols={"id_mutation", "code_commune", "valeur_fonciere"})

    for f in dgfip_files:
        _check_csv(f, sep="|", required_cols={"Code commune", "Valeur fonciere"})

    logger.info("[DVF Preprocess] Validation OK")


def _check_csv(path: Path, sep: str, required_cols: set[str]) -> None:
    size_mb = path.stat().st_size / 1e6
    if size_mb < 1:
        raise ValueError(f"Fichier trop petit ({size_mb:.0f} MB) — téléchargement incomplet ? {path.name}")

    try:
        df = pd.read_csv(path, sep=sep, nrows=100, dtype=str)
    except Exception as e:
        raise ValueError(f"Impossible de lire {path.name} : {e}") from e

    cols_lower = {c.lower() for c in df.columns}
    missing = {c for c in required_cols if c.lower() not in cols_lower}
    if missing:
        raise ValueError(
            f"Colonnes manquantes dans {path.name} : {missing}. Colonnes détectées : {list(df.columns)[:10]}"
        )

    logger.info(f"[DVF Preprocess] {path.name} OK ({size_mb:.0f} MB, {len(df.columns)} colonnes)")
