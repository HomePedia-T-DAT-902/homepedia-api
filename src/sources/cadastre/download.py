"""Téléchargement des parcelles cadastrales Etalab (1 fichier GeoJSON.gz / département)."""

import logging
from pathlib import Path

import requests

from src.sources.cadastre.config import CADASTRE_BASE, DEPARTEMENTS, RAW_DIR

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR, depts: list[str] | None = None, force: bool = False) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    targets = depts if depts else DEPARTEMENTS
    logger.info(f"[Cadastre Download] {len(targets)} département(s) à télécharger")

    downloaded = skipped = 0
    for i, dept in enumerate(targets, 1):
        logger.info(f"[{i}/{len(targets)}] Département {dept}")
        if _download_dept(raw_dir, dept, force=force):
            downloaded += 1
        else:
            skipped += 1

    logger.info(f"[Cadastre Download] {downloaded} téléchargés, {skipped} ignorés")


def _download_dept(raw_dir: Path, dept: str, force: bool = False) -> bool:
    dest = raw_dir / f"parcelles_{dept}.geojson.gz"
    if dest.exists() and not force:
        logger.info(f"  [{dept}] déjà présent, ignoré")
        return False

    url = CADASTRE_BASE.format(dept=dept)
    try:
        _download_raw_gz(url, dest)
        return True
    except Exception as e:
        logger.warning(f"  [{dept}] échec ({e}), ignoré.")
        if dest.exists():
            dest.unlink()
        return False


def _download_raw_gz(url: str, dest: Path, chunk_size: int = 1024 * 1024) -> None:
    """
    Télécharge en préservant les bytes gzip bruts.
    decode_content=False désactive la décompression automatique de requests :
    le serveur envoie Content-Encoding: gzip mais on veut conserver le .gz sur disque.
    """
    logger.info(f"Téléchargement : {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        r.raw.decode_content = False
        total = int(r.headers.get("content-length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            for chunk in r.raw.stream(chunk_size):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    print(
                        f"\r  {downloaded / total * 100:.1f}%  ({downloaded / 1e6:.0f} / {total / 1e6:.0f} MB)",
                        end="",
                        flush=True,
                    )
        print()

    logger.info(f"Sauvegardé : {dest}  ({dest.stat().st_size / 1e6:.0f} MB)")
