"""BPESource — orchestre download, preprocess, process, load pour la BPE."""

import logging
import os
from pathlib import Path

import psycopg2

from src.sources.base import DataSource
from src.sources.bpe import config
from src.sources.bpe import download, load, preprocess, process

logger = logging.getLogger(__name__)


class BPESource(DataSource):

    def __init__(
        self,
        raw_dir: Path = config.RAW_DIR,
        processed_dir: Path = config.PROCESSED_DIR,
    ):
        super().__init__(raw_dir, processed_dir)

    def download(self) -> None:
        logger.info("=== [BPE] Download ===")
        download.run(self.raw_dir)

    def preprocess(self) -> None:
        logger.info("=== [BPE] Preprocess ===")
        preprocess.run(self.raw_dir)

    def process(self) -> None:
        logger.info("=== [BPE] Process (Spark) ===")
        process.run(self.raw_dir, self.processed_dir)

    def load(self) -> None:
        logger.info("=== [BPE] Load (PostgreSQL) ===")
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
