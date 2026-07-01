"""Téléchargement des risques naturels et technologiques par commune (API Géorisques)."""

import csv
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from src.sources.risques.config import (
    COMMUNES_CSV,
    GEORISQUES_URL,
    MAX_WORKERS,
    OUTPUT_COLUMNS,
    PAUSE_BETWEEN_BATCHES,
    RAW_DIR,
    RAW_FILE,
    RISK_CODE_MAP,
    TECHNO_PREFIXES,
)

logger = logging.getLogger(__name__)


def _load_commune_codes(dept_filter: list[str] | None = None) -> list[str]:
    """Lit la liste des codes commune depuis le CSV Etalab."""
    if not COMMUNES_CSV.exists():
        raise FileNotFoundError(
            f"[Risques] Fichier communes introuvable : {COMMUNES_CSV}\nLancez d'abord la source 'geo'."
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

    logger.info(f"[Risques]  {len(codes):,} communes à traiter")
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
        logger.debug(f"[Risques] Erreur API pour {code_commune}: {exc}")
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


def run(raw_dir: Path = RAW_DIR, force: bool = False, dept_filter: list[str] | None = None) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / RAW_FILE
    if dest.exists() and not force:
        logger.info(f"[Risques] Déjà présent, ignoré : {dest}  (--force pour écraser)")
        return

    logger.info("=== [Risques] Téléchargement (API Géorisques) ===")
    codes = _load_commune_codes(dept_filter)

    results: list[dict] = []
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
                logger.info(f"[Risques]  {done:,} / {len(codes):,} communes traitées")

    with open(dest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"[Risques]  → {len(results):,} communes écrites dans {dest}")
