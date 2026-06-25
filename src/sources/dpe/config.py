from pathlib import Path

RAW_DIR = Path("data/raw/dpe")
PROCESSED_DIR = Path("data/processed/dpe")

ADEME_API_BASE = "https://data.ademe.fr/data-fair/api/v1/datasets"
DPE_NOUVEAU_DATASET_ID = "meg-83tjwtg8dyz4vv7h1dqe"
DPE_ANCIEN_DATASET_ID = "dpe-france"

DPE_NOUVEAU_COLS = "code_insee_ban,date_etablissement_dpe,etiquette_dpe,conso_5_usages_par_m2_ef"
DPE_ANCIEN_COLS = "code_insee_commune_actualise,date_etablissement_dpe,classe_consommation_energie,consommation_energie"
ADEME_PAGE_SIZE = 10_000

DPE_NOUVEAU_FILE = "dpe_nouveau.csv"
DPE_ANCIEN_FILE = "dpe_ancien.csv"

CONSO_MIN = 0
CONSO_MAX = 3_000
CLASSES_VALIDES = {"A", "B", "C", "D", "E", "F", "G"}

DIAG_OUTPUT_COLS = [
    "code_commune",
    "date_diagnostic",
    "classe_energie",
    "consommation_moyenne",
    "source",
]

COMMUNE_STATS_OUTPUT_COLS = [
    "code_commune",
    "nb_dpe_total",
    "nb_classe_a", "nb_classe_b", "nb_classe_c", "nb_classe_d",
    "nb_classe_e", "nb_classe_f", "nb_classe_g",
    "pct_classe_a", "pct_classe_b", "pct_classe_c", "pct_classe_d",
    "pct_classe_e", "pct_classe_f", "pct_classe_g",
    "consommation_moyenne_commune",
]
