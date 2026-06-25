"""IRISSource — orchestre download, preprocess, process, load pour les contours IRIS."""

import logging
import os
from pathlib import Path

import psycopg2

from src.sources.base import DataSource
from src.sources.iris import config
from src.sources.iris import download, load, preprocess, process

logger = logging.getLogger(__name__)


class IRISSource(DataSource):
    def __init__(self, raw_dir: Path = config.RAW_DIR, processed_dir: Path = Path("data/processed/iris")):
        super().__init__(raw_dir, processed_dir)

    def download(self) -> None:
        logger.info("=== [IRIS] Download ===")
        download.run(self.raw_dir)

    def preprocess(self) -> None:
        logger.info("=== [IRIS] Preprocess ===")
        preprocess.run(self.raw_dir)

    def process(self) -> None:
        process.run(self.raw_dir)

    def load(self) -> None:
        logger.info("=== [IRIS] Load (PostgreSQL) ===")
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ.get("POSTGRES_DB", "homepedia"),
            user=os.environ.get("POSTGRES_USER", "homepedia"),
            password=os.environ.get("POSTGRES_PASSWORD", "homepedia_secret"),
        )
        try:
            load.run(conn, self.raw_dir)
        finally:
            conn.close()
