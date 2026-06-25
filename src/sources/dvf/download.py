"""Téléchargement des données DVF (Geo-DVF Etalab + DVF brut DGFiP)."""

import logging
import shutil
import zipfile
from pathlib import Path

import requests

from src.sources.utils import decompress_gz, download_file
from src.sources.dvf.config import (
    DGFIP_DATASET_ID,
    DGFIP_YEARS,
    GEO_DVF_BASE,
    GEO_DVF_YEARS,
    RAW_DIR,
)

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR, since_year: int = 0, force: bool = False) -> None:
    download_geo_dvf(raw_dir, since_year=since_year, force=force)
    download_dgfip_dvf(raw_dir, since_year=since_year, force=force)


def download_geo_dvf(raw_dir: Path = RAW_DIR, since_year: int = 0, force: bool = False) -> None:
    """Geo-DVF Etalab (2020-2024, CSV UTF-8, géolocalisé)."""
    logger.info("=== [1/2] Geo-DVF Etalab ===")
    years = [y for y in GEO_DVF_YEARS if y >= since_year]
    if not years:
        logger.info("Aucune année Geo-DVF à télécharger.")
        return

    for year in years:
        dest = raw_dir / "geo" / f"dvf_{year}.csv"
        if dest.exists() and not force:
            logger.info(f"  {year} — déjà présent, ignoré")
            continue

        gz_url = f"{GEO_DVF_BASE}/{year}/full.csv.gz"
        gz_dest = dest.with_suffix(".csv.gz")
        try:
            download_file(gz_url, gz_dest)
            decompress_gz(gz_dest, dest)
        except requests.HTTPError as e:
            logger.warning(f"  {year} — échec ({e}), ignoré.")
            if gz_dest.exists():
                gz_dest.unlink()


def download_dgfip_dvf(raw_dir: Path = RAW_DIR, since_year: int = 0, force: bool = False) -> None:
    """DVF brut DGFiP — années non couvertes par Geo-DVF."""
    dgfip_only_years = [y for y in DGFIP_YEARS if y not in GEO_DVF_YEARS]
    years = [y for y in dgfip_only_years if y >= since_year]

    logger.info(f"=== [2/2] DVF brut DGFiP — années : {years or 'aucune'} ===")
    if not years:
        logger.info("  Toutes les années DGFiP sont couvertes par Geo-DVF.")
        return

    for year in years:
        dest = raw_dir / "dgfip" / f"dvf_{year}.csv"
        if dest.exists() and not force:
            logger.info(f"  {year} — déjà présent, ignoré")
            continue

        try:
            url = _get_dgfip_year_url(year)
        except RuntimeError as e:
            logger.warning(f"  {year} — URL introuvable : {e}")
            continue

        if url.endswith(".zip"):
            zip_dest = dest.with_suffix(".txt.zip")
            try:
                download_file(url, zip_dest)
                _extract_txt_from_zip(zip_dest, dest)
            except (requests.HTTPError, RuntimeError) as e:
                logger.warning(f"  {year} — échec ({e}), ignoré.")
                if zip_dest.exists():
                    zip_dest.unlink()
        elif url.endswith(".gz"):
            gz_dest = dest.with_suffix(".csv.gz")
            try:
                download_file(url, gz_dest)
                decompress_gz(gz_dest, dest)
            except requests.HTTPError as e:
                logger.warning(f"  {year} — échec ({e}), ignoré.")
                if gz_dest.exists():
                    gz_dest.unlink()
        else:
            try:
                download_file(url, dest)
            except requests.HTTPError as e:
                logger.warning(f"  {year} — échec ({e}), ignoré.")


def _get_dgfip_year_url(year: int) -> str:
    """Récupère l'URL du fichier DVF DGFiP pour une année via l'API data.gouv.fr."""
    api_url = f"https://www.data.gouv.fr/api/1/datasets/{DGFIP_DATASET_ID}/"
    r = requests.get(api_url, timeout=30)
    r.raise_for_status()

    resources = r.json().get("resources", [])
    if not resources:
        raise RuntimeError(f"Aucune ressource pour {DGFIP_DATASET_ID}")

    matches = [
        res for res in resources
        if str(year) in res.get("title", "") and "txt" in res.get("format", "").lower()
    ]
    if not matches:
        matches = [res for res in resources if str(year) in res.get("title", "")]
    if not matches:
        raise RuntimeError(
            f"Aucune ressource DVF DGFiP pour {year}. "
            f"Disponible : {[r.get('title') for r in resources if 'pdf' not in r.get('format', '').lower()]}"
        )

    full_year = [m for m in matches if "semestre" not in m.get("title", "").lower()]
    chosen = full_year[0] if full_year else matches[0]
    logger.info(f"  Ressource {year} : {chosen.get('title')} → {chosen['url']}")
    return chosen["url"]


def _extract_txt_from_zip(zip_path: Path, dest_csv: Path) -> None:
    """Extrait le .txt d'une archive .zip DGFiP et le renomme en .csv."""
    logger.info(f"Extraction zip : {zip_path.name}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        txt_files = [f for f in zf.namelist() if f.endswith(".txt")]
        if not txt_files:
            raise RuntimeError(f"Aucun fichier .txt dans {zip_path.name}")
        with zf.open(txt_files[0]) as src, open(dest_csv, "wb") as dst:
            shutil.copyfileobj(src, dst)
    zip_path.unlink()
    logger.info(f"Extrait : {dest_csv}  ({dest_csv.stat().st_size / 1e6:.0f} MB)")
