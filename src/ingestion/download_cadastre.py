"""
Téléchargement du cadastre — Parcelles cadastrales Etalab (P1-cadastre).

Source : Etalab — Plan cadastral informatisé
    URL par département : https://cadastre.data.gouv.fr/bundler/cadastre-etalab/departements/{dept}/geojson/parcelles
    Format : GeoJSON (gzip), 1 fichier par département
    Volume : ~70M parcelles, ~40-60 GB décompressé

Les fichiers sont stockés compressés (.geojson.gz) pour économiser l'espace disque.
Le loader les décompresse à la volée lors du chargement en base.

Usage :
    python -m src.ingestion.download_cadastre                    # tous les départements
    python -m src.ingestion.download_cadastre --dept 75          # Paris uniquement
    python -m src.ingestion.download_cadastre --dept 75 13 69    # Paris, BdR, Rhône
    python -m src.ingestion.download_cadastre --force            # re-télécharge tout
"""

import argparse
import logging
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/cadastre")

CADASTRE_BASE = "https://cadastre.data.gouv.fr/bundler/cadastre-etalab/departements/{dept}/geojson/parcelles"

# Tous les codes département France métropolitaine + DOM
DEPARTEMENTS = [
    *[f"{i:02d}" for i in range(1, 20)],   # 01-19
    "2A", "2B",                              # Corse
    *[f"{i:02d}" for i in range(21, 96)],   # 21-95
    "971", "972", "973", "974", "976",       # DOM
]


# ── Utilitaires ───────────────────────────────────────────────────────────────


def download_file(url: str, dest: Path, chunk_size: int = 1024 * 1024) -> None:
    """Télécharge un fichier vers dest avec affichage de la progression."""
    logger.info(f"Téléchargement : {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        # decode_content=False : désactive la décompression automatique de requests
        # pour conserver les bytes gzip bruts (Content-Encoding: gzip)
        r.raw.decode_content = False
        total = int(r.headers.get("content-length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            for chunk in r.raw.stream(chunk_size):
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


# ── Téléchargement ────────────────────────────────────────────────────────────


def download_dept(dept: str, force: bool = False) -> bool:
    """
    Télécharge le GeoJSON parcelles d'un département.
    Retourne True si téléchargé, False si ignoré.
    Les fichiers sont conservés en .geojson.gz (le loader décompresse à la volée).
    """
    dest = RAW_DIR / f"parcelles_{dept}.geojson.gz"

    if dest.exists() and not force:
        logger.info(f"  [{dept}] déjà présent, ignoré  (--force pour écraser)")
        return False

    url = CADASTRE_BASE.format(dept=dept)
    try:
        download_file(url, dest)
        return True
    except requests.HTTPError as e:
        logger.warning(f"  [{dept}] échec ({e}), ignoré.")
        if dest.exists():
            dest.unlink()
        return False
    except Exception as e:
        logger.warning(f"  [{dept}] erreur inattendue ({e}), ignoré.")
        if dest.exists():
            dest.unlink()
        return False


def download_all(depts: list[str], force: bool = False) -> None:
    """Télécharge les parcelles pour une liste de départements."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Dossier de sortie : {RAW_DIR.resolve()}")
    logger.info(f"{len(depts)} département(s) à télécharger")

    downloaded = 0
    skipped = 0

    for i, dept in enumerate(depts, 1):
        logger.info(f"[{i}/{len(depts)}] Département {dept}")
        if download_dept(dept, force=force):
            downloaded += 1
        else:
            skipped += 1

    logger.info("=== Téléchargement cadastre terminé ===")
    logger.info(f"  Téléchargés : {downloaded}  |  Ignorés : {skipped}")

    files = sorted(RAW_DIR.glob("parcelles_*.geojson.gz"))
    total_mb = sum(f.stat().st_size for f in files) / 1e6
    logger.info(f"  {len(files)} fichier(s) présents — {total_mb:.0f} MB total (compressé)")


# ── Entrée ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Téléchargement des parcelles cadastrales Etalab (1 fichier GeoJSON.gz / département)."
    )
    parser.add_argument(
        "--dept",
        nargs="+",
        metavar="DEPT",
        help="Code(s) département à télécharger (ex: 75 13 2A). Défaut : tous.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-télécharge même si le fichier existe déjà.",
    )
    args = parser.parse_args()

    depts = args.dept if args.dept else DEPARTEMENTS
    # Valider les codes fournis
    invalides = [d for d in depts if d not in DEPARTEMENTS]
    if invalides:
        parser.error(f"Code(s) département inconnu(s) : {invalides}. Attendus : {DEPARTEMENTS}")

    download_all(depts, force=args.force)


if __name__ == "__main__":
    main()
