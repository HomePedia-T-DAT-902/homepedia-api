"""Traitement : CSV → Parquet.

Pas de Spark ici — download.py produit déjà un CSV agrégé au niveau commune
(~35k lignes), un job distribué n'apporterait rien pour ce volume.
"""

import logging
from pathlib import Path

import pandas as pd

from src.sources.risques.config import PROCESSED_DIR, RAW_DIR, RAW_FILE

logger = logging.getLogger(__name__)

BOOL_COLUMNS = [
    "inondation",
    "seisme",
    "mouvement_terrain",
    "retrait_gonflement_argile",
    "radon",
    "feu_foret",
    "icpe",
]


def run(raw_dir: Path = RAW_DIR, processed_dir: Path = PROCESSED_DIR) -> None:
    src = raw_dir / RAW_FILE
    df = pd.read_csv(src, dtype={"code_commune": str})

    for col in BOOL_COLUMNS:
        df[col] = df[col].astype(str).str.strip().str.lower().isin(("true", "1", "oui"))

    processed_dir.mkdir(parents=True, exist_ok=True)
    out = processed_dir / "risques.parquet"
    df.to_parquet(out, index=False)
    logger.info(f"[Risques]  {len(df):,} communes → {out}")
