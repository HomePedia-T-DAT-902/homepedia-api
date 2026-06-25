"""Téléchargement des données DPE depuis l'API ADEME (paginée, cursor-based)."""

import csv
import logging
import urllib.parse
from pathlib import Path

import requests

from src.sources.dpe.config import (
    ADEME_API_BASE,
    ADEME_PAGE_SIZE,
    DPE_ANCIEN_COLS,
    DPE_ANCIEN_DATASET_ID,
    DPE_ANCIEN_FILE,
    DPE_NOUVEAU_COLS,
    DPE_NOUVEAU_DATASET_ID,
    DPE_NOUVEAU_FILE,
    RAW_DIR,
)

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR, force: bool = False) -> None:
    download_dpe_nouveau(raw_dir, force=force)
    download_dpe_ancien(raw_dir, force=force)


def download_dpe_nouveau(raw_dir: Path = RAW_DIR, force: bool = False) -> None:
    """DPE post-juillet 2021 — API ADEME paginée (~14M lignes)."""
    logger.info("=== [1/2] DPE nouveau (post-juillet 2021) — API ADEME ===")
    dest = raw_dir / DPE_NOUVEAU_FILE
    if dest.exists() and not force:
        logger.info(f"Déjà présent : {DPE_NOUVEAU_FILE}  (--force pour écraser)")
        return
    logger.info("  Note : ~14M lignes, téléchargement long (~1-2h selon débit).")
    _download_ademe_paginated(DPE_NOUVEAU_DATASET_ID, DPE_NOUVEAU_COLS, dest)


def download_dpe_ancien(raw_dir: Path = RAW_DIR, force: bool = False) -> None:
    """DPE pré-juillet 2021 — API ADEME paginée (~10.7M lignes)."""
    logger.info("=== [2/2] DPE ancien (pré-juillet 2021) — API ADEME ===")
    dest = raw_dir / DPE_ANCIEN_FILE
    if dest.exists() and not force:
        logger.info(f"Déjà présent : {DPE_ANCIEN_FILE}  (--force pour écraser)")
        return
    _download_ademe_paginated(DPE_ANCIEN_DATASET_ID, DPE_ANCIEN_COLS, dest)


def _download_ademe_paginated(dataset_id: str, select_cols: str, dest: Path) -> None:
    """
    Télécharge un dataset ADEME data-fair via pagination cursor-based.
    Écrit directement en CSV au fur et à mesure pour ne pas charger en mémoire.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    base_url = f"{ADEME_API_BASE}/{dataset_id}/lines"
    params: dict = {"size": ADEME_PAGE_SIZE, "select": select_cols}

    total_count = None
    written = 0
    after = None

    with open(dest, "w", newline="", encoding="utf-8") as out_f:
        writer = None

        while True:
            if after:
                params["after"] = after

            r = requests.get(base_url, params=params, timeout=60)
            r.raise_for_status()
            data = r.json()

            if total_count is None:
                total_count = data.get("total", "?")
                logger.info(
                    f"  Total ADEME : {total_count:,}"
                    if isinstance(total_count, int)
                    else f"  Total : {total_count}"
                )

            results = data.get("results", [])
            if not results:
                break

            if writer is None:
                writer = csv.DictWriter(out_f, fieldnames=list(results[0].keys()))
                writer.writeheader()

            writer.writerows(results)
            written += len(results)

            next_url = data.get("next")
            if next_url:
                qs = urllib.parse.urlparse(next_url).query
                after = urllib.parse.parse_qs(qs).get("after", [None])[0]
            else:
                after = None

            if written % 500_000 < ADEME_PAGE_SIZE:
                pct = f" ({written / total_count * 100:.0f}%)" if isinstance(total_count, int) and total_count else ""
                logger.info(f"  → {written:,} lignes{pct}")

            if not after:
                break

    logger.info(f"  Terminé : {written:,} lignes → {dest}  ({dest.stat().st_size / 1e6:.0f} MB)")
