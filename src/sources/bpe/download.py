"""Téléchargement de la BPE depuis data.gouv.fr."""

import logging
from pathlib import Path

import requests

from src.sources.bpe.config import CSV_FILE, DATASET_ID, PARQUET_FILE, RAW_DIR
from src.sources.utils import decompress_gz, download_file

logger = logging.getLogger(__name__)


def get_resource_url() -> tuple[str, str]:
    """Récupère l'URL du fichier BPE via l'API data.gouv.fr. Préfère Parquet, fallback CSV."""
    api_url = f"https://www.data.gouv.fr/api/1/datasets/{DATASET_ID}/"
    r = requests.get(api_url, timeout=30)
    r.raise_for_status()
    resources = r.json().get("resources", [])

    for res in resources:
        if "parquet" in res.get("format", "").lower() or "parquet" in res.get("url", "").lower():
            return res["url"], res.get("title", "BPE")

    for res in resources:
        url = res.get("url", "")
        if "csv" in res.get("format", "").lower() or url.endswith((".csv", ".csv.gz")):
            return url, res.get("title", "BPE")

    res = resources[0]
    logger.warning(f"Format inconnu, première ressource utilisée : {res.get('title')}")
    return res["url"], res.get("title", "BPE")


def run(raw_dir: Path = RAW_DIR, force: bool = False) -> None:
    """Télécharge le fichier BPE (Parquet → CSV)."""
    csv_dest = raw_dir / CSV_FILE
    parquet_dest = raw_dir / PARQUET_FILE

    if csv_dest.exists() and not force:
        logger.info(f"BPE déjà présent : {csv_dest}  (--force pour écraser)")
        return

    raw_dir.mkdir(parents=True, exist_ok=True)
    url, title = get_resource_url()
    logger.info(f"Ressource sélectionnée : {title}")

    if "parquet" in url.lower():
        download_file(url, parquet_dest)
        _convert_parquet_to_csv(parquet_dest, csv_dest)
    elif url.endswith(".gz"):
        gz_dest = csv_dest.with_suffix(".csv.gz")
        download_file(url, gz_dest)
        decompress_gz(gz_dest, csv_dest)
    else:
        download_file(url, csv_dest)

    logger.info(f"BPE téléchargé : {csv_dest}")


def _convert_parquet_to_csv(parquet_path: Path, csv_dest: Path) -> None:
    try:
        import pandas as pd
        df = pd.read_parquet(parquet_path)
        df.to_csv(csv_dest, index=False, sep=";")
        parquet_path.unlink()
        logger.info(f"Converti Parquet → CSV : {len(df):,} lignes")
    except ImportError:
        logger.warning("pandas non disponible — Parquet conservé (Spark peut le lire).")
        parquet_path.rename(csv_dest.with_suffix(".parquet"))
