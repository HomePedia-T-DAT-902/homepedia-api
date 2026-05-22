"""
Download IRIS boundaries (infra-communal districts) from IGN WFS.

Source: IGN — Contours IRIS (INSEE/IGN) via WFS service
    WFS: https://data.geopf.fr/wfs/ows
    Layer: STATISTICALUNITS.IRIS:contours_iris
    Format: GeoJSON (EPSG:4326)
    Volume: ~49 000 IRIS polygons

IRIS (Ilots Regroupes pour l'Information Statistique) is the sub-communal
breakdown used by INSEE for communes with 10,000+ inhabitants (~2,000 people
per IRIS). code_iris = code_commune (5 chars) + IRIS number (4 chars).

The WFS always serves the latest edition — no need to track yearly archives.

Usage:
    python -m src.ingestion.download_iris                  # download if missing
    python -m src.ingestion.download_iris --force          # re-download
"""

import argparse
import json
import logging
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/iris")
DEST_FILE = "contours-iris.geojson"

WFS_BASE = "https://data.geopf.fr/wfs/ows"
WFS_LAYER = "STATISTICALUNITS.IRIS:contours_iris"
PAGE_SIZE = 5_000  # WFS pagination — max features per request


def fetch_iris_page(start_index: int) -> dict:
    """Fetch a page of IRIS features from the WFS."""
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


def download_iris(force: bool = False) -> None:
    """Download all IRIS boundaries via WFS pagination."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / DEST_FILE

    if dest.exists() and not force:
        logger.info(f"Already present: {dest}  (--force to re-download)")
        return

    logger.info(f"Output directory: {RAW_DIR.resolve()}")
    logger.info(f"Fetching IRIS from WFS: {WFS_BASE} (layer: {WFS_LAYER})")

    all_features = []
    start_index = 0

    while True:
        logger.info(f"  Fetching features {start_index} to {start_index + PAGE_SIZE}...")
        data = fetch_iris_page(start_index)

        features = data.get("features", [])
        if not features:
            break

        all_features.extend(features)
        logger.info(f"  Received {len(features)} features (total: {len(all_features)})")

        if len(features) < PAGE_SIZE:
            break

        start_index += PAGE_SIZE

    geojson = {
        "type": "FeatureCollection",
        "features": all_features,
    }

    dest.write_text(json.dumps(geojson), encoding="utf-8")
    logger.info(f"Saved: {dest}  ({dest.stat().st_size / 1e6:.1f} MB, {len(all_features)} features)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download IGN Contours IRIS (infra-communal boundaries) via WFS.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if files already exist.",
    )
    args = parser.parse_args()

    download_iris(force=args.force)
    logger.info("=== IRIS download complete ===")


if __name__ == "__main__":
    main()
