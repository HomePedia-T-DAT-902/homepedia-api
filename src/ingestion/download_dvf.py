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
import zipfile
from datetime import date
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/dvf")

# ── Geo-DVF Etalab (2020 → présent, CSV UTF-8) ───────────────────────────────
GEO_DVF_BASE = "https://files.data.gouv.fr/geo-dvf/latest/csv"
GEO_DVF_YEARS = list(range(2020, 2025))  # mettre à jour quand 2025 est publié

# ── DVF brut DGFiP (2020-2025, txt.zip Latin-1, séparateur |) ───────────────
# NOTE : les données pré-2020 ne sont plus disponibles sur data.gouv.fr.
# Le dataset DGFiP couvre désormais 2020-2025 (chevauchement avec Geo-DVF).
# On ne télécharge que les années absentes de Geo-DVF (ex: 2025 S1).
DGFIP_DATASET_ID = "5c4ae55a634f4117716d5656"
DGFIP_YEARS = list(range(2020, 2026))  # sera filtré selon GEO_DVF_YEARS


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
    Les ressources sont nommées "Valeurs foncières {year}" dans le TITRE (pas dans l'URL).
    Format : .txt.zip (archive zip contenant un .txt séparé par |, encodage Latin-1).
    """
    api_url = f"https://www.data.gouv.fr/api/1/datasets/{DGFIP_DATASET_ID}/"
    logger.info(f"API data.gouv.fr — dataset DVF DGFiP : {api_url}")
    r = requests.get(api_url, timeout=30)
    r.raise_for_status()

    resources = r.json().get("resources", [])
    if not resources:
        raise RuntimeError(f"Aucune ressource trouvée pour le dataset {DGFIP_DATASET_ID}")

    # L'année est dans le TITRE (ex: "Valeurs foncières 2024"), pas dans l'URL
    # On prend la ressource txt.zip dont le titre contient l'année
    matches = []
    for res in resources:
        title = res.get("title", "")
        fmt = res.get("format", "")
        if str(year) in title and "txt" in fmt.lower():
            matches.append(res)

    if not matches:
        # Fallback : chercher juste l'année dans le titre (sans filtrer par format)
        matches = [res for res in resources if str(year) in res.get("title", "")]

    if not matches:
        raise RuntimeError(
            f"Aucune ressource DVF DGFiP pour l'année {year}. "
            f"Disponible : {[r.get('title') for r in resources if 'pdf' not in r.get('format','').lower()]}"
        )

    # Si plusieurs (ex: "2020 - Second semestre"), prendre l'année complète en priorité
    full_year = [m for m in matches if str(year) in m.get("title", "") and "semestre" not in m.get("title", "").lower()]
    chosen = full_year[0] if full_year else matches[0]
    logger.info(f"  Ressource {year} trouvée : {chosen.get('title')}  →  {chosen['url']}")
    return chosen["url"]


def extract_txt_from_zip(zip_path: Path, dest_csv: Path) -> None:
    """
    Extrait le fichier .txt d'une archive .zip DGFiP et le renomme en .csv.
    Le .txt est en Latin-1 avec séparateur | — on le copie tel quel (spark_dvf le gère).
    Supprime le zip après extraction.
    """
    logger.info(f"Extraction zip : {zip_path.name}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        txt_files = [f for f in zf.namelist() if f.endswith(".txt")]
        if not txt_files:
            raise RuntimeError(f"Aucun fichier .txt dans {zip_path.name}")
        txt_name = txt_files[0]
        logger.info(f"  Fichier extrait : {txt_name} → {dest_csv.name}")
        with zf.open(txt_name) as src, open(dest_csv, "wb") as dst:
            shutil.copyfileobj(src, dst)
    zip_path.unlink()
    logger.info(f"Extrait : {dest_csv}  ({dest_csv.stat().st_size / 1e6:.0f} MB)")


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
    """
    DVF brut DGFiP (format txt.zip, Latin-1, séparateur |).
    Ne télécharge que les années absentes de Geo-DVF (pour éviter les doublons).
    """
    # Les années déjà couvertes par Geo-DVF sont inutiles en DGFiP
    dgfip_only_years = [y for y in DGFIP_YEARS if y not in GEO_DVF_YEARS]
    years = [y for y in dgfip_only_years if y >= since_year]

    logger.info(f"=== [2/2] DVF brut DGFiP — années hors Geo-DVF : {years or 'aucune'} ===")
    if not years:
        logger.info("  Toutes les années DGFiP sont déjà couvertes par Geo-DVF. Rien à télécharger.")
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

        # Format DGFiP : .txt.zip (zip contenant un .txt)
        if url.endswith(".zip"):
            zip_dest = dest.with_suffix(".txt.zip")
            try:
                download_file(url, zip_dest)
                extract_txt_from_zip(zip_dest, dest)
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
