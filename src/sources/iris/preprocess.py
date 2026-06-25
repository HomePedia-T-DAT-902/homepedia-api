"""Validation du fichier IRIS avant chargement."""

import json
import logging
from pathlib import Path

from src.sources.iris.config import DEST_FILE, RAW_DIR

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR) -> None:
    """Vérifie que le GeoJSON IRIS est présent et lisible."""
    path = raw_dir / DEST_FILE

    if not path.exists():
        raise ValueError(f"Fichier IRIS absent : {path}. Lancer download() d'abord.")

    size_mb = path.stat().st_size / 1e6
    if size_mb < 1:
        raise ValueError(f"Fichier trop petit ({size_mb:.1f} MB) — téléchargement incomplet ?")

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        nb = len(data.get("features", []))
    except Exception as e:
        raise ValueError(f"Impossible de lire {path.name} : {e}") from e

    if nb < 1_000:
        raise ValueError(f"Trop peu de features IRIS ({nb}) — fichier corrompu ?")

    logger.info(f"[IRIS Preprocess] {path.name} OK — {nb:,} features, {size_mb:.1f} MB")
