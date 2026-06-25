"""Shared paths and JSON Lines helpers for the ville-ideale pipeline.

The pipeline is a 4-stage chain, each stage reading the previous stage's file and
writing its own (so any stage can be run on its own):

    download   -> data/raw/ville_ideale/{cities,reviews}.jsonl
    preprocess -> data/processed/ville_ideale/communes.jsonl
    process    -> data/processed/ville_ideale/communes_enriched.jsonl
    load       -> PostgreSQL table city_reviews
"""

import json
from pathlib import Path

RAW_DIR = Path("data/raw/ville_ideale")
PROCESSED_DIR = Path("data/processed/ville_ideale")

RAW_CITIES = RAW_DIR / "cities.jsonl"
RAW_REVIEWS = RAW_DIR / "reviews.jsonl"
PREPROCESSED = PROCESSED_DIR / "communes.jsonl"
ENRICHED = PROCESSED_DIR / "communes_enriched.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSON Lines file into a list of dicts (empty list if the file is absent)."""
    if not Path(path).exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Write a list of dicts as a JSON Lines file (creating parent dirs as needed)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")
