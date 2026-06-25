"""Pas de traitement Spark pour les contours IRIS — chargement direct du GeoJSON."""

import logging
from pathlib import Path

from src.sources.iris.config import RAW_DIR

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR) -> None:
    logger.info("[IRIS] Pas de traitement Spark — chargement direct du GeoJSON en base")
