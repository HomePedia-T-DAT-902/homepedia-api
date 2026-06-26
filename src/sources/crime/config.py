"""Configuration de la source Délinquance (SSMSI)."""

from pathlib import Path

RAW_DIR = Path("data/raw/crime")
PROCESSED_DIR = Path("data/processed/crime")
RAW_FILE = "crime_communal.parquet"

# data.gouv.fr — slug du dataset SSMSI
DATASET_SLUG = (
    "bases-statistiques-communale-departementale-et-regionale-de-la-"
    "delinquance-enregistree-par-la-police-et-la-gendarmerie-nationales"
)

CODGEO_COL = "CODGEO_2025"

# Regroupement des 15 indicateurs en 5 catégories
INDICATEURS_CAMBRIOLAGES = ["Cambriolages de logement"]

INDICATEURS_VIOLENCES = [
    "Violences physiques intrafamiliales",
    "Violences physiques hors cadre familial",
    "Violences sexuelles",
]

INDICATEURS_VOLS = [
    "Vols avec armes",
    "Vols violents sans arme",
    "Vols sans violence contre des personnes",
    "Vols de véhicule",
    "Vols dans les véhicules",
    "Vols d'accessoires sur véhicules",
]

INDICATEURS_STUPS = [
    "Trafic de stupéfiants",
    "Usage de stupéfiants",
    "Usage de stupéfiants (AFD)",
]

INDICATEURS_DESTRUCTIONS = ["Destructions et dégradations volontaires"]

CATEGORIES = {
    "cambriolages": INDICATEURS_CAMBRIOLAGES,
    "violences": INDICATEURS_VIOLENCES,
    "vols": INDICATEURS_VOLS,
    "stups": INDICATEURS_STUPS,
    "destructions": INDICATEURS_DESTRUCTIONS,
}
