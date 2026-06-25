"""
Téléchargement des risques naturels et technologiques par commune.

Source : API Géorisques — https://www.data.gouv.fr/dataservices/api-georisques
         BRGM / Ministère de la Transition Écologique

Approche : appels à l'API Géorisques par commune (concurrents, limités à 5 req/s).
Sortie   : data/raw/risques/commune_risques.csv

Usage :
    python -m src.ingestion.download_risques
    python -m src.ingestion.download_risques --force
    python -m src.ingestion.download_risques --dept 75 13 69
"""

import argparse
import csv
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/risques")
DEST_FILE = RAW_DIR / "commune_risques.csv"
COMMUNES_CSV = Path("data/raw/geo/communes-france-2025.csv")

GEORISQUES_URL = "https://georisques.gouv.fr/api/v1/gaspar/risques"
MAX_WORKERS = 5
PAUSE_BETWEEN_BATCHES = 1.0  # secondes

# num_risque → colonne CSV  (vérifié sur l'API réelle)
RISK_CODE_MAP = {
    "11": "inondation",
    "12": "mouvement_terrain",
    "13": "seisme",
    "14": "retrait_gonflement_argile",
    "15": "feu_foret",
    "16": "radon",
}
TECHNO_PREFIXES = ("2",)  # codes 2x = risques technologiques (TMD, ICPE...)

OUTPUT_COLUMNS = [
    "code_commune",
    "inondation",
    "seisme",
    "mouvement_terrain",
    "retrait_gonflement_argile",
    "radon",
    "feu_foret",
    "icpe",
]


def _load_commune_codes(dept_filter: list[str] | None = None) -> list[str]:
    """Lit la liste des codes commune depuis le CSV Etalab."""
    if not COMMUNES_CSV.exists():
        raise FileNotFoundError(
            f"Fichier communes introuvable : {COMMUNES_CSV}\n"
            "Lancez d'abord : python -m src.ingestion.download_geo"
        )

    codes = []
    with open(COMMUNES_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = (row.get("code_commune") or row.get("code_insee") or "").strip()
            if not code or len(code) != 5:
                continue
            if dept_filter and code[:2] not in dept_filter and code[:3] not in dept_filter:
                continue
            codes.append(code)

    logger.info(f"  {len(codes):,} communes à traiter")
    return codes


def _fetch_risques(code_commune: str) -> dict:
    """
    Appelle l'API Géorisques pour une commune.

    Réponse attendue :
    {
      "data": [{
        "code_insee": "75056",
        "risques_detail": [
          {"num_risque": "11", "libelle_risque_long": "Inondation", ...},
          ...
        ]
      }]
    }
    """
    row: dict = {col: False for col in OUTPUT_COLUMNS}
    row["code_commune"] = code_commune

    try:
        resp = requests.get(
            GEORISQUES_URL,
            params={"code_insee": code_commune, "page": 1, "page_size": 100},
            timeout=15,
        )
        if resp.status_code == 404:
            return row
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug(f"  Erreur API pour {code_commune}: {exc}")
        return row

    communes_data = data.get("data", [])
    if not communes_data:
        return row

    for risque in communes_data[0].get("risques_detail", []):
        num = str(risque.get("num_risque", "")).strip()
        colonne = RISK_CODE_MAP.get(num)
        if colonne:
            row[colonne] = True
        elif any(num.startswith(p) for p in TECHNO_PREFIXES):
            row["icpe"] = True

    return row


def download_risques(force: bool = False, dept_filter: list[str] | None = None) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if DEST_FILE.exists() and not force:
        logger.info(f"Déjà présent, ignoré : {DEST_FILE}  (--force pour écraser)")
        return

    logger.info("=== Téléchargement des risques (API Géorisques) ===")
    codes = _load_commune_codes(dept_filter)

    results: list[dict] = []
    errors = 0
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_risques, code): code for code in codes}
        batch_count = 0
        for future in as_completed(futures):
            results.append(future.result())
            done += 1
            batch_count += 1
            if batch_count >= MAX_WORKERS * 10:
                time.sleep(PAUSE_BETWEEN_BATCHES)
                batch_count = 0
            if done % 1000 == 0:
                logger.info(f"  {done:,} / {len(codes):,} communes traitées ({errors} erreurs)")

    with open(DEST_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"  → {len(results):,} communes écrites dans {DEST_FILE}")
    logger.info(f"  → {errors} erreurs API")


def main() -> None:
    parser = argparse.ArgumentParser(description="Téléchargement des risques par commune (Géorisques).")
    parser.add_argument("--force", action="store_true", help="Re-télécharge même si le fichier existe.")
    parser.add_argument("--dept", nargs="+", metavar="DEPT", help="Restreindre à ces départements.")
    args = parser.parse_args()

    download_risques(force=args.force, dept_filter=args.dept)


if __name__ == "__main__":
    main()
