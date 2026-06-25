"""Validation des fichiers cadastre (GeoJSON.gz) avant chargement."""

import logging
from pathlib import Path

from src.sources.cadastre.config import RAW_DIR

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR, depts: list[str] | None = None) -> None:
    """Vérifie que les fichiers GeoJSON.gz sont présents et non tronqués."""
    if depts:
        files = [raw_dir / f"parcelles_{d}.geojson.gz" for d in depts]
    else:
        files = sorted(raw_dir.glob("parcelles_*.geojson.gz"))

    if not files:
        raise ValueError(f"Aucun fichier cadastre dans {raw_dir}. Lancer download() d'abord.")

    missing = [f for f in files if not f.exists()]
    if missing:
        raise ValueError(f"Fichiers absents : {[f.name for f in missing]}")

    small = [f for f in files if f.stat().st_size < 1_000]
    if small:
        raise ValueError(f"Fichiers suspectement petits (< 1 KB) : {[f.name for f in small]}")

    total_mb = sum(f.stat().st_size for f in files) / 1e6
    logger.info(f"[Cadastre Preprocess] {len(files)} fichier(s) OK — {total_mb:.0f} MB total (compressé)")
