"""Téléchargement des contours IRIS depuis le service WFS IGN (paginé)."""

import json
import logging
from pathlib import Path

import requests

from src.sources.iris.config import DEST_FILE, PAGE_SIZE, RAW_DIR, WFS_BASE, WFS_LAYER

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR, force: bool = False) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / DEST_FILE

    if dest.exists() and not force:
        logger.info(f"[IRIS Download] Déjà présent : {dest}  (--force pour écraser)")
        return

    logger.info(f"[IRIS Download] Récupération WFS : {WFS_BASE} (layer: {WFS_LAYER})")

    all_features = []
    start_index = 0

    while True:
        logger.info(f"  Features {start_index} → {start_index + PAGE_SIZE}...")
        data = _fetch_page(start_index)
        features = data.get("features", [])
        if not features:
            break

        all_features.extend(features)
        logger.info(f"  {len(features)} features reçues (total : {len(all_features)})")

        if len(features) < PAGE_SIZE:
            break
        start_index += PAGE_SIZE

    geojson = {"type": "FeatureCollection", "features": all_features}
    dest.write_text(json.dumps(geojson), encoding="utf-8")
    logger.info(f"[IRIS Download] {len(all_features)} features → {dest}  ({dest.stat().st_size / 1e6:.1f} MB)")


def _fetch_page(start_index: int) -> dict:
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": WFS_LAYER,
        "OUTPUTFORMAT": "application/json",
        "SRSNAME": "EPSG:4326",
        "COUNT": str(PAGE_SIZE),
        "STARTINDEX": str(start_index),
    }
    r = requests.get(WFS_BASE, params=params, timeout=120)
    r.raise_for_status()
    return r.json()
