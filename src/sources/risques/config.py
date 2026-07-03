"""Configuration de la source Risques naturels et technologiques (API Géorisques)."""

from pathlib import Path

RAW_DIR = Path("data/raw/risques")
PROCESSED_DIR = Path("data/processed/risques")

RAW_FILE = "commune_risques.csv"
COMMUNES_CSV = Path("data/raw/geo/communes-france-2025.csv")

GEORISQUES_URL = "https://georisques.gouv.fr/api/v1/gaspar/risques"
GEORISQUES_MVT_URL = "https://georisques.gouv.fr/api/v1/mvt"
GEORISQUES_CAVITES_URL = "https://georisques.gouv.fr/api/v1/cavites"
GEORISQUES_ICPE_URL = "https://georisques.gouv.fr/api/v1/installations_classees"
MAX_WORKERS = 5
PAUSE_BETWEEN_BATCHES = 1.0  # secondes

GEOPOINTS_FILE = "risques_geopoints.csv"
GEOPOINTS_COLUMNS = ["type_risque", "longitude", "latitude", "code_commune"]

# num_risque → colonne CSV  (vérifié sur l'API réelle)
RISK_CODE_MAP = {
    "11": "inondation",
    "12": "mouvement_terrain",
    "13": "seisme",
    "14": "retrait_gonflement_argile",
    "15": "feu_foret",
    "16": "radon",
}
TECHNO_PREFIXES = ("2",)  # codes 2x = risques technologiques (TMD, ICPE...)

OUTPUT_COLUMNS = [
    "code_commune",
    "inondation",
    "seisme",
    "mouvement_terrain",
    "retrait_gonflement_argile",
    "radon",
    "feu_foret",
    "icpe",
]
