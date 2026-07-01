"""Traitement : CSV → Parquet.

Pas de Spark ici — download.py produit déjà un CSV agrégé au niveau commune
(~35k lignes), un job distribué n'apporterait rien pour ce volume.
"""

import logging
from pathlib import Path

import pandas as pd

from src.sources.qualite_air.config import PROCESSED_DIR, RAW_DIR, RAW_FILE

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR, processed_dir: Path = PROCESSED_DIR) -> None:
    src = raw_dir / RAW_FILE
    df = pd.read_csv(src, dtype={"code_commune": str})

    processed_dir.mkdir(parents=True, exist_ok=True)
    out = processed_dir / "qualite_air.parquet"
    df.to_parquet(out, index=False)
    logger.info(f"[QualiteAir]  {len(df):,} communes → {out}")
