"""Configuration de la source Éducation (résultats du baccalauréat par commune)."""

from pathlib import Path

RAW_DIR = Path("data/raw/education")
PROCESSED_DIR = Path("data/processed/education")

# IVAL — Indicateurs de Valeur Ajoutée des Lycées (bac GT)
IVAL_DATASET_SLUG = "indicateurs-de-valeur-ajoutee-des-lycees-denseignement-general-et-technologique-ancien"
IVAL_FILE = "ival.csv"

# Colonnes IVAL utiles
IVAL_CODE_COL = "Code commune"
IVAL_YEAR_COL = "Annee"
IVAL_PRESENTS_COL = "Presents - Toutes series"
IVAL_TAUX_COL = "Taux de reussite - Toutes series"
