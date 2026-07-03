"""Téléchargement des geopoints de risques depuis l'API Géorisques.

Endpoints utilisés (par commune) :
  - /api/v1/mvt                   → mouvement_terrain
  - /api/v1/cavites               → cavite
  - /api/v1/installations_classees → icpe

Les risques zonaux (séisme, inondation, radon, feu_foret, retrait_gonflement_argile)
ne disposent pas de geopoints individuels dans l'API Géorisques ; ils sont traités
via centroïde commune dans load.py.
"""

import csv
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from src.sources.risques.config import (
    COMMUNES_CSV,
    GEOPOINTS_COLUMNS,
    GEOPOINTS_FILE,
    GEORISQUES_CAVITES_URL,
    GEORISQUES_ICPE_URL,
    GEORISQUES_MVT_URL,
    MAX_WORKERS,
    PAUSE_BETWEEN_BATCHES,
    RAW_DIR,
)

logger = logging.getLogger(__name__)

_PAGE_SIZE = 100
_ENDPOINTS = [
    (GEORISQUES_MVT_URL, "mouvement_terrain"),
    (GEORISQUES_CAVITES_URL, "cavite"),
    (GEORISQUES_ICPE_URL, "icpe"),
]


def _load_commune_codes() -> list[str]:
    if not COMMUNES_CSV.exists():
        raise FileNotFoundError(
            f"[Risques/Geopoints] Fichier communes introuvable : {COMMUNES_CSV}\n"
            "Lancez d'abord la source 'geo'."
        )
    codes = []
    with open(COMMUNES_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = (row.get("code_commune") or row.get("code_insee") or "").strip()
            if code and len(code) == 5:
                codes.append(code)
    logger.info(f"[Risques/Geopoints] {len(codes):,} communes à traiter")
    return codes


def _fetch_commune(code_commune: str) -> list[dict]:
    """Récupère tous les geopoints pour une commune (MVT + cavités + ICPE)."""
    points = []

    for url, type_risque in _ENDPOINTS:
        page = 1
        while True:
            try:
                resp = requests.get(
                    url,
                    params={"code_insee": code_commune, "page_size": _PAGE_SIZE, "page": page},
                    timeout=15,
                )
                if resp.status_code in (404, 500):
                    break
                resp.raise_for_status()
                payload = resp.json()
            except Exception as exc:
                logger.debug(f"[Risques/Geopoints] {code_commune}/{type_risque} p{page}: {exc}")
                break

            for item in payload.get("data", []):
                lon = item.get("longitude")
                lat = item.get("latitude")
                if lon is None or lat is None:
                    continue
                points.append({
                    "type_risque": type_risque,
                    "longitude": float(lon),
                    "latitude": float(lat),
                    "code_commune": code_commune,
                })

            total_pages = payload.get("total_pages", 0)
            if page >= total_pages:
                break
            page += 1

    return points


def run(raw_dir: Path = RAW_DIR, force: bool = False) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / GEOPOINTS_FILE
    if dest.exists() and not force:
        logger.info(f"[Risques/Geopoints] Déjà présent, ignoré : {dest}  (--force pour écraser)")
        return

    logger.info("=== [Risques] Téléchargement geopoints (API Géorisques) ===")
    codes = _load_commune_codes()

    all_points: list[dict] = []
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_commune, code): code for code in codes}
        batch_count = 0
        for future in as_completed(futures):
            all_points.extend(future.result())
            done += 1
            batch_count += 1
            if batch_count >= MAX_WORKERS * 10:
                time.sleep(PAUSE_BETWEEN_BATCHES)
                batch_count = 0
            if done % 1000 == 0:
                logger.info(f"[Risques/Geopoints] {done:,} / {len(codes):,} communes — {len(all_points):,} points collectés")

    with open(dest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=GEOPOINTS_COLUMNS)
        writer.writeheader()
        writer.writerows(all_points)

    logger.info(f"[Risques/Geopoints] → {len(all_points):,} geopoints écrits dans {dest}")
