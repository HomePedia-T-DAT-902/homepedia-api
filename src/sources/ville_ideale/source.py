"""VilleIdealeSource — orchestre download, preprocess, process, load pour ville-ideale.fr.

Avis citoyens scrapés sur ville-ideale.fr (notes sur 9 critères + texte). Particularité
vs les autres sources : pas de fichier bulk à télécharger mais du scraping page par page,
et un mode *on-demand* (``on_demand.py``) utilisé par l'API pour charger une commune à la
volée. Le pipeline batch ci-dessous sert au pré-remplissage.
"""

import logging
import os
from pathlib import Path

import psycopg2

from src.sources.base import DataSource
from src.sources.ville_ideale import config, download, load, preprocess, process

logger = logging.getLogger(__name__)


class VilleIdealeSource(DataSource):
    def __init__(
        self,
        raw_dir: Path = config.RAW_DIR,
        processed_dir: Path = config.PROCESSED_DIR,
    ):
        super().__init__(raw_dir, processed_dir)

    def download(self) -> None:
        logger.info("=== [ville-ideale] Download (scraping) ===")
        download.run(self.raw_dir)

    def preprocess(self) -> None:
        logger.info("=== [ville-ideale] Preprocess ===")
        preprocess.run(self.raw_dir)

    def process(self) -> None:
        logger.info("=== [ville-ideale] Process (word cloud) ===")
        process.run(self.raw_dir, self.processed_dir)

    def load(self) -> None:
        logger.info("=== [ville-ideale] Load (PostgreSQL) ===")
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ.get("POSTGRES_DB", "homepedia"),
            user=os.environ.get("POSTGRES_USER", "homepedia"),
            password=os.environ.get("POSTGRES_PASSWORD", "homepedia_secret"),
        )
        try:
            load.run(conn, self.processed_dir)
        finally:
            conn.close()
