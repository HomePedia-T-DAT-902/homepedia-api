"""
Téléchargement des données géographiques de référence (P1-1).

Sources :
- Contours administratifs (communes, depts, régions) — Etalab/IGN
- Attributs communes (nom, codes, coords, superficie...) — "Communes et villes de France"
- Population municipale 2023 — INSEE via data.gouv.fr

Usage :
    python -m src.ingestion.download_geo                  # télécharge uniquement ce qui manque
    python -m src.ingestion.download_geo --force          # re-télécharge tout
    python -m src.ingestion.download_geo --source contours
    python -m src.ingestion.download_geo --source communes
    python -m src.ingestion.download_geo --source population
"""

import argparse
import gzip
import logging
import shutil
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/geo")

# ── Etalab contours 2025 ──────────────────────────────────────────────────────
ETALAB_BASE = "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/geojson"

CONTOURS_FILES = [
    ("communes-5m.geojson.gz", "communes-5m.geojson"),
    ("communes-50m.geojson.gz", "communes-50m.geojson"),
    ("departements-5m.geojson.gz", "departements-5m.geojson"),
    ("regions-5m.geojson.gz", "regions-5m.geojson"),
]

# ── Communes et villes de France (CSV.gz) ─────────────────────────────────────
# NOTE : URL hardcodée avec l'année 2025 dans le chemin.
# Quand une version 2026 sera publiée, mettre à jour COMMUNES_CSV_URL et COMMUNES_CSV_DEST.
# Page du dataset : https://www.data.gouv.fr/datasets/communes-et-villes-de-france-en-csv-excel-json-parquet-et-feather/
COMMUNES_CSV_URL = (
    "https://static.data.gouv.fr/resources/"
    "communes-et-villes-de-france-en-csv-excel-json-parquet-et-feather/"
    "20250221-162608/communes-france-2025.csv.gz"
)
COMMUNES_CSV_DEST = "communes-france-2025.csv"

# ── Population municipale INSEE ───────────────────────────────────────────────
POPULATION_DATASET_ID = "65b1a75854fb88f787f72944"
POPULATION_DEST = "population-municipale.xlsx"


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
                    print(f"\r  {pct:.1f}%  ({downloaded / 1e6:.1f} MB / {total / 1e6:.1f} MB)", end="", flush=True)
        print()

    logger.info(f"Sauvegardé : {dest}  ({dest.stat().st_size / 1e6:.1f} MB)")


def decompress_gz(gz_path: Path, dest_path: Path) -> None:
    """Décompresse un fichier .gz vers dest_path puis supprime le .gz."""
    logger.info(f"Décompression : {gz_path.name} → {dest_path.name}")
    with gzip.open(gz_path, "rb") as f_in, open(dest_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    gz_path.unlink()
    logger.info(f"Extrait : {dest_path}  ({dest_path.stat().st_size / 1e6:.1f} MB)")


def get_datagouv_resource_url(dataset_id: str, format_hint: str = "xlsx") -> str:
    """
    Récupère l'URL de téléchargement du fichier principal d'un dataset data.gouv.fr.
    Cherche d'abord par format, prend la ressource la plus récente.
    """
    api_url = f"https://www.data.gouv.fr/api/1/datasets/{dataset_id}/"
    logger.info(f"Interrogation API data.gouv.fr : {api_url}")
    r = requests.get(api_url, timeout=30)
    r.raise_for_status()

    resources = r.json().get("resources", [])
    if not resources:
        raise RuntimeError(f"Aucune ressource trouvée pour le dataset {dataset_id}")

    # Filtrer par format et prendre la plus récente (dernière dans la liste)
    matching = [
        res
        for res in resources
        if format_hint.lower() in res.get("format", "").lower() or format_hint.lower() in res.get("url", "").lower()
    ]
    candidates = matching if matching else resources
    chosen = candidates[-1]  # la plus récente

    url = chosen["url"]
    logger.info(f"Ressource sélectionnée : {chosen.get('title', '?')}  →  {url}")
    return url


# ── Sources ───────────────────────────────────────────────────────────────────


def download_contours(force: bool = False) -> None:
    """Contours administratifs Etalab (communes, depts, régions)."""
    logger.info("=== [1/3] Contours administratifs (Etalab) ===")

    for gz_name, dest_name in CONTOURS_FILES:
        dest = RAW_DIR / dest_name
        if dest.exists() and not force:
            logger.info(f"Déjà présent, ignoré : {dest_name}  (--force pour écraser)")
            continue

        gz_dest = RAW_DIR / gz_name
        download_file(f"{ETALAB_BASE}/{gz_name}", gz_dest)
        decompress_gz(gz_dest, dest)


def download_communes(force: bool = False) -> None:
    """Attributs communes (nom, codes, coords, superficie...) depuis le CSV Etalab."""
    logger.info("=== [2/3] Attributs communes (Communes et villes de France) ===")

    dest = RAW_DIR / COMMUNES_CSV_DEST
    if dest.exists() and not force:
        logger.info(f"Déjà présent, ignoré : {COMMUNES_CSV_DEST}  (--force pour écraser)")
        return

    gz_dest = dest.with_suffix(".csv.gz")
    download_file(COMMUNES_CSV_URL, gz_dest)
    decompress_gz(gz_dest, dest)


def download_population(force: bool = False) -> None:
    """Population municipale 2023 (p23_pop) — INSEE via data.gouv.fr."""
    logger.info("=== [3/3] Population municipale INSEE ===")

    dest = RAW_DIR / POPULATION_DEST
    if dest.exists() and not force:
        logger.info(f"Déjà présent, ignoré : {POPULATION_DEST}  (--force pour écraser)")
        return

    url = get_datagouv_resource_url(POPULATION_DATASET_ID, format_hint="xlsx")
    download_file(url, dest)


# ── Entrée ────────────────────────────────────────────────────────────────────

SOURCES = {
    "contours": download_contours,
    "communes": download_communes,
    "population": download_population,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Téléchargement des données géographiques de référence.")
    parser.add_argument(
        "--source",
        choices=list(SOURCES.keys()),
        help="Télécharge uniquement cette source (par défaut : toutes).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-télécharge même si le fichier existe déjà.",
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Dossier de sortie : {RAW_DIR.resolve()}")

    if args.source:
        SOURCES[args.source](force=args.force)
    else:
        for fn in SOURCES.values():
            fn(force=args.force)

    logger.info("=== Téléchargement terminé ===")
    logger.info("Fichiers disponibles :")
    for f in sorted(RAW_DIR.iterdir()):
        logger.info(f"  {f.name}  ({f.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
