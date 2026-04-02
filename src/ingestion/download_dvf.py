"""
Téléchargement des données DVF — Demandes de Valeurs Foncières (P1-2).

2 sources distinctes selon la période :
- Geo-DVF (Etalab, 2020-2024) : CSV UTF-8, géolocalisé, 1 fichier/an
    URL : https://files.data.gouv.fr/geo-dvf/latest/csv/{year}/full.csv.gz
- DVF brut (DGFiP, 2014-2019) : CSV Latin-1, séparateur `|`, 1 fichier/an
    Dataset data.gouv.fr : 5c4ae55a634f4117716d5656

Volume total : ~8-10 GB, 25-30M lignes

Usage :
    python -m src.ingestion.download_dvf                        # toutes les années
    python -m src.ingestion.download_dvf --since 2022-01-01    # à partir de 2022
    python -m src.ingestion.download_dvf --force               # re-télécharge tout
    python -m src.ingestion.download_dvf --source geo          # Geo-DVF uniquement
    python -m src.ingestion.download_dvf --source dgfip        # DVF brut uniquement
"""

import argparse
import gzip
import logging
import shutil
from datetime import date
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/dvf")

# ── Geo-DVF Etalab (2020 → présent, CSV UTF-8) ───────────────────────────────
GEO_DVF_BASE = "https://files.data.gouv.fr/geo-dvf/latest/csv"
GEO_DVF_YEARS = list(range(2020, 2025))  # mettre à jour quand 2025 est publié

# ── DVF brut DGFiP (2014-2019, CSV Latin-1, séparateur |) ────────────────────
DGFIP_DATASET_ID = "5c4ae55a634f4117716d5656"
DGFIP_YEARS = list(range(2014, 2020))


# ── Utilitaires ───────────────────────────────────────────────────────────────


def download_file(url: str, dest: Path, chunk_size: int = 1024 * 1024) -> None:
    """Télécharge un fichier vers dest avec affichage de la progression."""
    logger.info(f"Téléchargement : {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=300) as r:
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


def get_dgfip_year_url(year: int) -> str:
    """
    Récupère l'URL du fichier DVF DGFiP pour une année donnée via l'API data.gouv.fr.
    Les ressources sont nommées "Demandes de valeurs foncières {year}" ou similaire.
    """
    api_url = f"https://www.data.gouv.fr/api/1/datasets/{DGFIP_DATASET_ID}/"
    logger.info(f"API data.gouv.fr — dataset DVF DGFiP : {api_url}")
    r = requests.get(api_url, timeout=30)
    r.raise_for_status()

    resources = r.json().get("resources", [])
    if not resources:
        raise RuntimeError(f"Aucune ressource trouvée pour le dataset {DGFIP_DATASET_ID}")

    # Chercher la ressource contenant l'année dans le titre ou l'URL
    for res in resources:
        title = res.get("title", "")
        url = res.get("url", "")
        if str(year) in title or str(year) in url:
            logger.info(f"  Ressource {year} trouvée : {title}  →  {url}")
            return url

    raise RuntimeError(
        f"Aucune ressource DVF DGFiP pour l'année {year}. "
        f"Vérifier manuellement sur data.gouv.fr/fr/datasets/{DGFIP_DATASET_ID}"
    )


def year_from_since(since: str | None) -> int:
    """Retourne l'année minimale à télécharger depuis --since YYYY-MM-DD."""
    if since is None:
        return 0
    return date.fromisoformat(since).year


# ── Sources ───────────────────────────────────────────────────────────────────


def download_geo_dvf(since_year: int = 0, force: bool = False) -> None:
    """Geo-DVF Etalab (2020-2024, CSV UTF-8, géolocalisé)."""
    logger.info("=== [1/2] Geo-DVF Etalab (2020-2024) ===")

    years = [y for y in GEO_DVF_YEARS if y >= since_year]
    if not years:
        logger.info("Aucune année Geo-DVF à télécharger selon --since.")
        return

    for year in years:
        dest = RAW_DIR / "geo" / f"dvf_{year}.csv"
        if dest.exists() and not force:
            logger.info(f"  {year} — déjà présent, ignoré  (--force pour écraser)")
            continue

        gz_url = f"{GEO_DVF_BASE}/{year}/full.csv.gz"
        gz_dest = dest.with_suffix(".csv.gz")
        try:
            download_file(gz_url, gz_dest)
            decompress_gz(gz_dest, dest)
        except requests.HTTPError as e:
            logger.warning(f"  {year} — échec téléchargement ({e}), ignoré.")
            if gz_dest.exists():
                gz_dest.unlink()


def download_dgfip_dvf(since_year: int = 0, force: bool = False) -> None:
    """DVF brut DGFiP (2014-2019, CSV Latin-1, séparateur |)."""
    logger.info("=== [2/2] DVF brut DGFiP (2014-2019) ===")

    years = [y for y in DGFIP_YEARS if y >= since_year]
    if not years:
        logger.info("Aucune année DVF DGFiP à télécharger selon --since.")
        return

    for year in years:
        dest = RAW_DIR / "dgfip" / f"dvf_{year}.csv"
        if dest.exists() and not force:
            logger.info(f"  {year} — déjà présent, ignoré  (--force pour écraser)")
            continue

        try:
            url = get_dgfip_year_url(year)
        except RuntimeError as e:
            logger.warning(f"  {year} — URL introuvable : {e}")
            continue

        # Les fichiers DGFiP sont parfois déjà décompressés, parfois en .gz
        if url.endswith(".gz"):
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


# ── Entrée ────────────────────────────────────────────────────────────────────

SOURCES = {
    "geo": download_geo_dvf,
    "dgfip": download_dgfip_dvf,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Téléchargement des données DVF (2014-2024).")
    parser.add_argument(
        "--source",
        choices=list(SOURCES.keys()),
        help="geo = Etalab 2020-2024 | dgfip = DGFiP 2014-2019 (défaut : les deux).",
    )
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        help="Télécharge uniquement les fichiers >= cette date (ex: 2022-01-01).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-télécharge même si le fichier existe déjà.",
    )
    args = parser.parse_args()

    since_year = year_from_since(args.since)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Dossier de sortie : {RAW_DIR.resolve()}")
    if since_year:
        logger.info(f"Mode incrémental : années >= {since_year}")

    if args.source:
        SOURCES[args.source](since_year=since_year, force=args.force)
    else:
        download_geo_dvf(since_year=since_year, force=args.force)
        download_dgfip_dvf(since_year=since_year, force=args.force)

    logger.info("=== Téléchargement DVF terminé ===")
    for subdir in sorted(RAW_DIR.iterdir()):
        if subdir.is_dir():
            files = sorted(subdir.iterdir())
            total_mb = sum(f.stat().st_size for f in files) / 1e6
            logger.info(f"  {subdir.name}/  — {len(files)} fichier(s), {total_mb:.0f} MB total")


if __name__ == "__main__":
    main()
