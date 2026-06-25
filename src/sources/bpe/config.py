"""Constantes et configuration de la source BPE."""

from pathlib import Path

# ── Chemins ───────────────────────────────────────────────────────────────────
RAW_DIR = Path("data/raw/bpe")
PROCESSED_DIR = Path("data/processed/bpe")
CSV_FILE = "bpe.csv"
PARQUET_FILE = "bpe.parquet"

# ── API data.gouv.fr ──────────────────────────────────────────────────────────
DATASET_ID = "69ca8e301e273a3a7f32ee61"

# ── Colonnes attendues après normalisation ────────────────────────────────────
EXPECTED_COLUMNS = ["code_commune", "typequ"]
MIN_ROWS = 1_000_000  # ~1.8M équipements en 2024

# ── Grandes catégories BPE (première lettre du TYPEQU) ───────────────────────
CATEGORIES = ["A", "B", "C", "D", "E", "F"]

# ── Types d'équipements clés pour l'évaluation immobilière ───────────────────
TYPEQU_CLES = {
    "nb_maternelles": ["A101"],
    "nb_primaires": ["A104"],
    "nb_creches": ["A111"],
    "nb_colleges": ["A203"],
    "nb_lycees": ["A206", "A207"],
    "nb_medecins": ["D201"],
    "nb_pharmacies": ["D232"],
    "nb_urgences": ["D101"],
    "nb_supermarches": ["C201"],
    "nb_hypermarches": ["C101"],
    "nb_gares": ["E102"],
}

OUTPUT_COLUMNS = (
    ["code_commune", "nb_equipements_total"]
    + [f"nb_{cat.lower()}" for cat in CATEGORIES]
    + list(TYPEQU_CLES.keys())
)
