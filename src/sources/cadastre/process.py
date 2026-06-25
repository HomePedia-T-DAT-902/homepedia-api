"""Pas de traitement Spark pour le cadastre — les GeoJSON.gz sont chargés directement."""

import logging
from pathlib import Path

from src.sources.cadastre.config import RAW_DIR

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR) -> None:
    logger.info("[Cadastre] Pas de traitement Spark — chargement direct des GeoJSON.gz en base")
