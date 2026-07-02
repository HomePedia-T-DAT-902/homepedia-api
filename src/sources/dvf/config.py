from pathlib import Path

RAW_DIR = Path("data/raw/dvf")
PROCESSED_DIR = Path("data/processed/dvf")

GEO_DVF_BASE = "https://files.data.gouv.fr/geo-dvf/latest/csv"
GEO_DVF_YEARS = [2024]

DGFIP_DATASET_ID = "5c4ae55a634f4117716d5656"
DGFIP_YEARS = []

PRIX_M2_MIN = 100
PRIX_M2_MAX = 100_000
SURFACE_MIN = 5
SURFACE_MAX = 10_000
PRIX_MIN = 1_000

OUTPUT_COLS = [
    "id_mutation",
    "date_mutation",
    "nature_mutation",
    "valeur_fonciere",
    "code_commune",
    "type_local",
    "surface_reelle_bati",
    "nombre_pieces_principales",
    "surface_terrain",
    "longitude",
    "latitude",
    "annee",
    "prix_m2",
    "source",
]
