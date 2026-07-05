"""Configuration de la source Qualité de l'air (indice ATMO — ATMO France / data.gouv.fr)."""

from pathlib import Path

RAW_DIR = Path("data/raw/qualite_air")
PROCESSED_DIR = Path("data/processed/qualite_air")

RAW_FILE = "commune_qualite_air.csv"

# Dataset data.gouv.fr : Indice ATMO France
ATMO_DATASET_ID = "6149925a2ff0ab6cebdd6fe8"

# Mapping libellé qualité → colonne cible (ordre croissant de pollution)
QUALIF_COLUMN_MAP = {
    "bon": "nb_jours_bon",
    "moyen": "nb_jours_moyen",
    "dégradé": "nb_jours_degrade",
    "degrade": "nb_jours_degrade",
    "mauvais": "nb_jours_mauvais",
    "très mauvais": "nb_jours_tres_mauvais",
    "tres mauvais": "nb_jours_tres_mauvais",
    "extrêmement mauvais": "nb_jours_extremement_mauvais",
    "extremement mauvais": "nb_jours_extremement_mauvais",
}

OUTPUT_COLUMNS = [
    "code_commune",
    "annee",
    "indice_atmo",
    "nb_jours_bon",
    "nb_jours_moyen",
    "nb_jours_degrade",
    "nb_jours_mauvais",
    "nb_jours_tres_mauvais",
    "nb_jours_extremement_mauvais",
]
