"""Téléchargement du fichier IVAL (résultats bac) depuis data.gouv.fr."""

import logging
from pathlib import Path

import requests

from src.sources.education.config import IVAL_DATASET_SLUG, IVAL_FILE, RAW_DIR
from src.sources.utils import download_file

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR, force: bool = False) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / IVAL_FILE
    if dest.exists() and not force:
        logger.info(f"[Education] Déjà présent : {dest}  (--force pour écraser)")
        return
    url = _get_csv_url(IVAL_DATASET_SLUG)
    download_file(url, dest)
    logger.info(f"[Education] Téléchargé : {dest}  ({dest.stat().st_size / 1e6:.1f} MB)")


def _get_csv_url(slug: str) -> str:
    api_url = f"https://www.data.gouv.fr/api/1/datasets/{slug}/"
    r = requests.get(api_url, timeout=30)
    r.raise_for_status()
    resources = r.json().get("resources", [])

    # Préfère le CSV "toutes séries" / ensemble
    for res in resources:
        fmt = res.get("format", "").lower()
        title = res.get("title", "").lower()
        url = res.get("url", "")
        if "csv" in fmt and ("toutes" in title or "ensemble" in title or "all" in title):
            logger.info(f"[Education] Ressource : {res.get('title')} → {url}")
            return url

    # Fallback : premier CSV disponible
    for res in resources:
        if "csv" in res.get("format", "").lower():
            logger.info(f"[Education] Ressource (fallback) : {res.get('title')} → {res['url']}")
            return res["url"]

    raise RuntimeError(
        f"[Education] Aucune ressource CSV trouvée. "
        f"Disponibles : {[r.get('title') for r in resources]}"
    )
