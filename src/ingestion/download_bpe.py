"""
Téléchargement de la BPE — Base Permanente des Équipements (P1-4).

Source : INSEE via data.gouv.fr
    Dataset correct (Parquet) : https://www.data.gouv.fr/datasets/base-permanente-des-equipements-3
    ID : 69ca8e301e273a3a7f32ee61

Note : l'ancien dataset "base-permanente-des-equipements-1" ne fournit qu'un lien vers
une page web INSEE (pas un fichier direct). Le bon dataset fournit un Parquet (~200MB).
Le Parquet est converti en CSV pour cohérence avec le reste du pipeline.

Colonnes clés :
    - DEPCOM  → code_commune INSEE (5 chars, clé de jointure)
    - TYPEQU  → code type d'équipement (229 types : A101=maternelle, D201=médecin, E101=gare…)
    Une ligne par équipement — l'agrégation par commune se fait dans spark_aggregations.py.

Usage :
    python -m src.ingestion.download_bpe          # télécharge si absent
    python -m src.ingestion.download_bpe --force  # re-télécharge
"""

import argparse
import gzip
import logging
import shutil
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/bpe")
BPE_DEST = "bpe.csv"

# Dataset data.gouv.fr avec fichier Parquet direct (BPE24.parquet)
# Page : https://www.data.gouv.fr/datasets/base-permanente-des-equipements-3
BPE_DATASET_ID = "69ca8e301e273a3a7f32ee61"
BPE_PARQUET_DEST = "bpe.parquet"


# ── Utilitaires ───────────────────────────────────────────────────────────────


def download_file(url: str, dest: Path, chunk_size: int = 1024 * 1024) -> None:
    """Télécharge un fichier vers dest avec affichage de la progression."""
    logger.info(f"Téléchargement : {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(
                        f"\r  {pct:.1f}%  ({downloaded / 1e6:.0f} MB / {total / 1e6:.0f} MB)",
                        end="",
                        flush=True,
                    )
        print()

    logger.info(f"Sauvegardé : {dest}  ({dest.stat().st_size / 1e6:.0f} MB)")


def decompress_gz(gz_path: Path, dest_path: Path) -> None:
    """Décompresse un fichier .gz vers dest_path puis supprime le .gz."""
    logger.info(f"Décompression : {gz_path.name} → {dest_path.name}")
    with gzip.open(gz_path, "rb") as f_in, open(dest_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    gz_path.unlink()
    logger.info(f"Extrait : {dest_path}  ({dest_path.stat().st_size / 1e6:.0f} MB)")


def get_bpe_resource_url() -> tuple[str, str]:
    """
    Récupère l'URL du fichier BPE principal via l'API data.gouv.fr.
    Préfère le fichier CSV complet (toutes communes, pas par département).
    Retourne (url, title).
    """
    api_url = f"https://www.data.gouv.fr/api/1/datasets/{BPE_DATASET_ID}/"
    logger.info(f"API data.gouv.fr : {api_url}")
    r = requests.get(api_url, timeout=30)
    r.raise_for_status()

    resources = r.json().get("resources", [])
    if not resources:
        raise RuntimeError(f"Aucune ressource pour le dataset {BPE_DATASET_ID}")

    # Chercher Parquet en priorité (le dataset fournit BPE24.parquet)
    for res in resources:
        fmt = res.get("format", "").lower()
        url_lower = res.get("url", "").lower()
        if "parquet" in fmt or "parquet" in url_lower:
            logger.info(f"Ressource Parquet sélectionnée : {res.get('title')}  →  {res['url']}")
            return res["url"], res.get("title", "BPE")

    # Fallback CSV
    for res in resources:
        fmt = res.get("format", "").lower()
        url_lower = res.get("url", "").lower()
        if "csv" in fmt or "csv" in url_lower or "gz" in url_lower:
            logger.info(f"Ressource CSV fallback : {res.get('title')}  →  {res['url']}")
            return res["url"], res.get("title", "BPE")

    # Dernier recours : première ressource
    res = resources[0]
    logger.warning(f"Format inconnu, on prend la première ressource : {res.get('title')}")
    return res["url"], res.get("title", "BPE")


# ── Source principale ─────────────────────────────────────────────────────────


def download_bpe(force: bool = False) -> None:
    """Télécharge le fichier BPE (Parquet, dernier millésime, toutes communes)."""
    logger.info("=== BPE — Base Permanente des Équipements ===")

    parquet_dest = RAW_DIR / BPE_PARQUET_DEST
    csv_dest = RAW_DIR / BPE_DEST

    if csv_dest.exists() and not force:
        logger.info(f"Déjà présent, ignoré : {BPE_DEST}  (--force pour écraser)")
        _log_summary(csv_dest)
        return

    url, title = get_bpe_resource_url()
    logger.info(f"Fichier : {title}")

    if "parquet" in url.lower():
        download_file(url, parquet_dest)
        _convert_parquet_to_csv(parquet_dest, csv_dest)
    elif url.endswith(".gz"):
        gz_dest = csv_dest.with_suffix(".csv.gz")
        download_file(url, gz_dest)
        decompress_gz(gz_dest, csv_dest)
    else:
        download_file(url, csv_dest)

    _log_summary(csv_dest)


def _convert_parquet_to_csv(parquet_path: Path, csv_dest: Path) -> None:
    """Convertit le Parquet BPE en CSV pour cohérence avec le pipeline."""
    try:
        import pandas as pd

        logger.info(f"Conversion Parquet → CSV : {parquet_path.name}")
        df = pd.read_parquet(parquet_path)
        df.to_csv(csv_dest, index=False, sep=";")
        parquet_path.unlink()
        logger.info(f"Converti : {len(df):,} lignes → {csv_dest.name}")
    except ImportError:
        # pandas non installé → garder le Parquet, spark peut le lire directement
        logger.warning("pandas non disponible — Parquet conservé tel quel (Spark peut le lire).")
        parquet_path.rename(csv_dest.with_suffix(".parquet"))


def _log_summary(path: Path) -> None:
    """Affiche un résumé rapide du fichier téléchargé."""
    size_mb = path.stat().st_size / 1e6
    with open(path, "rb") as f:
        nb_lines = sum(1 for _ in f)
    logger.info(f"Résumé : {nb_lines - 1:,} équipements  |  {size_mb:.0f} MB")
    logger.info("Rappel colonnes clés : DEPCOM (code_commune), TYPEQU (229 types)")
    logger.info("Agrégation par commune dans spark_aggregations.py")


# ── Entrée ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Téléchargement de la BPE — Base Permanente des Équipements (INSEE).")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-télécharge même si le fichier existe déjà.",
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Dossier de sortie : {RAW_DIR.resolve()}")

    download_bpe(force=args.force)

    logger.info("=== Téléchargement BPE terminé ===")


if __name__ == "__main__":
    main()
