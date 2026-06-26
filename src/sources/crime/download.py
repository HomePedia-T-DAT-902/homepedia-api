"""Téléchargement du fichier délinquance communale (SSMSI) depuis data.gouv.fr."""

import logging
from pathlib import Path

import requests

from src.sources.crime.config import DATASET_SLUG, RAW_DIR, RAW_FILE
from src.sources.utils import download_file

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR, force: bool = False) -> None:
    dest = raw_dir / RAW_FILE
    if dest.exists() and not force:
        logger.info(f"[Crime] Déjà présent : {dest}  (--force pour écraser)")
        return

    raw_dir.mkdir(parents=True, exist_ok=True)
    url = _get_resource_url()
    download_file(url, dest)
    logger.info(f"[Crime] Téléchargé : {dest}  ({dest.stat().st_size / 1e6:.0f} MB)")


def _get_resource_url() -> str:
    """Récupère l'URL du fichier Parquet communal via l'API data.gouv.fr."""
    api_url = f"https://www.data.gouv.fr/api/1/datasets/{DATASET_SLUG}/"
    r = requests.get(api_url, timeout=30)
    r.raise_for_status()
    resources = r.json().get("resources", [])

    # Cherche le fichier Parquet au niveau communal (pas département/région)
    candidates = []
    for res in resources:
        title = res.get("title", "").lower()
        fmt = res.get("format", "").lower()
        url = res.get("url", "").lower()
        is_parquet = "parquet" in fmt or "parquet" in url or "parquet" in title
        is_commune = "comm" in title and "dep" not in title and "reg" not in title
        if is_parquet and is_commune:
            candidates.append(res)

    if not candidates:
        # Fallback : premier Parquet disponible
        candidates = [r for r in resources if "parquet" in r.get("format", "").lower()]

    if not candidates:
        raise RuntimeError(
            f"Aucune ressource Parquet trouvée dans le dataset SSMSI. "
            f"Ressources disponibles : {[r.get('title') for r in resources]}"
        )

    # Préférer le plus récent (dernière mise à jour)
    chosen = sorted(candidates, key=lambda r: r.get("last_modified", ""), reverse=True)[0]
    logger.info(f"[Crime] Ressource sélectionnée : {chosen.get('title')} → {chosen['url']}")
    return chosen["url"]
