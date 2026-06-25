from pathlib import Path

RAW_DIR = Path("data/raw/cadastre")

CADASTRE_BASE = "https://cadastre.data.gouv.fr/bundler/cadastre-etalab/departements/{dept}/geojson/parcelles"

DEPARTEMENTS = [
    *[f"{i:02d}" for i in range(1, 20)],
    "2A",
    "2B",
    *[f"{i:02d}" for i in range(21, 96)],
    "971",
    "972",
    "973",
    "974",
    "976",
]

BATCH_SIZE = 50_000
