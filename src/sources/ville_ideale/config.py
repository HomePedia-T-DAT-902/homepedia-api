"""Constantes et configuration de la source ville-ideale.fr."""

from pathlib import Path

# ── Chemins ───────────────────────────────────────────────────────────────────
RAW_DIR = Path("data/raw/ville_ideale")
PROCESSED_DIR = Path("data/processed/ville_ideale")

# ── Noms de fichiers par étape ────────────────────────────────────────────────
CITIES_FILE = "cities.jsonl"  # download   -> raw_dir
REVIEWS_FILE = "reviews.jsonl"  # download   -> raw_dir
COMMUNES_FILE = "communes.jsonl"  # preprocess -> raw_dir (nettoyé)
ENRICHED_FILE = "communes_enriched.jsonl"  # process    -> processed_dir
