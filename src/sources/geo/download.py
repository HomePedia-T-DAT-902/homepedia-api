"""Téléchargement des données géographiques de référence."""

import logging

import requests

from src.sources.geo.config import (
    COMMUNES_CSV_FILE, COMMUNES_CSV_URL, CONTOURS_FILES,
    ETALAB_BASE, POPULATION_DATASET_ID, POPULATION_FILE, RAW_DIR,
)
from src.sources.utils import decompress_gz, download_file

logger = logging.getLogger(__name__)


def run(raw_dir=RAW_DIR, force: bool = False) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    _download_contours(raw_dir, force)
    _download_communes_csv(raw_dir, force)
    _download_population(raw_dir, force)


def _download_contours(raw_dir, force: bool) -> None:
    logger.info("=== [GEO 1/3] Contours administratifs (Etalab) ===")
    for gz_name, dest_name in CONTOURS_FILES:
        dest = raw_dir / dest_name
        if dest.exists() and not force:
            logger.info(f"Déjà présent : {dest_name}")
            continue
        download_file(f"{ETALAB_BASE}/{gz_name}", raw_dir / gz_name)
        decompress_gz(raw_dir / gz_name, dest)


def _download_communes_csv(raw_dir, force: bool) -> None:
    logger.info("=== [GEO 2/3] Attributs communes ===")
    dest = raw_dir / COMMUNES_CSV_FILE
    if dest.exists() and not force:
        logger.info(f"Déjà présent : {COMMUNES_CSV_FILE}")
        return
    gz = dest.with_suffix(".csv.gz")
    download_file(COMMUNES_CSV_URL, gz)
    decompress_gz(gz, dest)


def _download_population(raw_dir, force: bool) -> None:
    logger.info("=== [GEO 3/3] Population municipale INSEE ===")
    dest = raw_dir / POPULATION_FILE
    if dest.exists() and not force:
        logger.info(f"Déjà présent : {POPULATION_FILE}")
        return
    url = _get_datagouv_url(POPULATION_DATASET_ID, "xlsx")
    download_file(url, dest)


def _get_datagouv_url(dataset_id: str, format_hint: str) -> str:
    r = requests.get(f"https://www.data.gouv.fr/api/1/datasets/{dataset_id}/", timeout=30)
    r.raise_for_status()
    resources = r.json().get("resources", [])
    matching = [res for res in resources if format_hint in res.get("format", "").lower()]
    chosen = (matching or resources)[-1]
    return chosen["url"]
