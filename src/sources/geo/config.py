"""Constantes et configuration de la source GEO."""

from pathlib import Path
from pyspark.sql.types import DoubleType, StringType, StructField, StructType

RAW_DIR = Path("data/raw/geo")
PROCESSED_DIR = Path("data/processed/geo")

# ── Contours Etalab 2025 ──────────────────────────────────────────────────────
ETALAB_BASE = "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/geojson"
CONTOURS_FILES = [
    ("communes-5m.geojson.gz", "communes-5m.geojson"),
    ("communes-50m.geojson.gz", "communes-50m.geojson"),
    ("departements-5m.geojson.gz", "departements-5m.geojson"),
    ("regions-5m.geojson.gz", "regions-5m.geojson"),
]

# ── CSV communes ──────────────────────────────────────────────────────────────
COMMUNES_CSV_URL = (
    "https://static.data.gouv.fr/resources/"
    "communes-et-villes-de-france-en-csv-excel-json-parquet-et-feather/"
    "20250221-162608/communes-france-2025.csv.gz"
)
COMMUNES_CSV_FILE = "communes-france-2025.csv"

# ── Population INSEE ──────────────────────────────────────────────────────────
POPULATION_DATASET_ID = "65b1a75854fb88f787f72944"
POPULATION_FILE = "population-municipale.xlsx"

# ── Fichiers attendus pour le preprocess ─────────────────────────────────────
REQUIRED_FILES = [
    "communes-5m.geojson",
    "communes-50m.geojson",
    "departements-5m.geojson",
    "regions-5m.geojson",
    COMMUNES_CSV_FILE,
    POPULATION_FILE,
]
COMMUNES_CSV_REQUIRED_COLS = {"code_insee", "nom_standard", "dep_code", "reg_code"}

# ── Schémas Spark ─────────────────────────────────────────────────────────────
POPULATION_SCHEMA = StructType(
    [
        StructField("codgeo", StringType(), True),
        StructField("p23_pop", DoubleType(), True),
    ]
)
