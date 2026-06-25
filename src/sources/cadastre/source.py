"""CadastreSource — orchestre download, preprocess, process, load pour les parcelles cadastrales."""

import logging
import os
from pathlib import Path

import psycopg2

from src.sources.base import DataSource
from src.sources.cadastre import config
from src.sources.cadastre import download, load, preprocess, process

logger = logging.getLogger(__name__)


class CadastreSource(DataSource):

    def __init__(
        self,
        raw_dir: Path = config.RAW_DIR,
        processed_dir: Path = Path("data/processed/cadastre"),
        depts: list[str] | None = None,
    ):
        super().__init__(raw_dir, processed_dir)
        self.depts = depts

    def download(self) -> None:
        logger.info("=== [Cadastre] Download ===")
        download.run(self.raw_dir, depts=self.depts)

    def preprocess(self) -> None:
        logger.info("=== [Cadastre] Preprocess ===")
        preprocess.run(self.raw_dir, depts=self.depts)

    def process(self) -> None:
        process.run(self.raw_dir)

    def load(self) -> None:
        logger.info("=== [Cadastre] Load (PostgreSQL) ===")
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ.get("POSTGRES_DB", "homepedia"),
            user=os.environ.get("POSTGRES_USER", "homepedia"),
            password=os.environ.get("POSTGRES_PASSWORD", "homepedia_secret"),
        )
        try:
            load.run(conn, self.raw_dir, depts=self.depts)
        finally:
            conn.close()
