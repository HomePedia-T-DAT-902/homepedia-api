"""Téléchargement de l'indice ATMO (qualité de l'air) par commune.

Source : ATMO France / data.gouv.fr — indices journaliers de qualité de l'air par commune.
Approche : téléchargement du CSV annuel le plus récent, agrégation par commune.
"""

import csv
import logging
import re
from pathlib import Path

import requests

from src.sources.qualite_air.config import ATMO_DATASET_ID, OUTPUT_COLUMNS, QUALIF_COLUMN_MAP, RAW_DIR, RAW_FILE
from src.sources.utils import download_file

logger = logging.getLogger(__name__)


def _get_atmo_csv_url(annee: int | None = None) -> tuple[str, str]:
    """Récupère l'URL du CSV ATMO le plus récent (ou pour l'année demandée)."""
    api_url = f"https://www.data.gouv.fr/api/1/datasets/{ATMO_DATASET_ID}/"
    logger.info(f"[QualiteAir] Interrogation data.gouv.fr : {api_url}")
    r = requests.get(api_url, timeout=30)
    r.raise_for_status()

    resources = r.json().get("resources", [])
    csv_resources = [
        res
        for res in resources
        if "csv" in res.get("format", "").lower() or res.get("url", "").lower().endswith(".csv")
    ]

    if not csv_resources:
        raise RuntimeError(f"[QualiteAir] Aucune ressource CSV trouvée pour le dataset {ATMO_DATASET_ID}")

    if annee:
        matching = [r for r in csv_resources if str(annee) in r.get("title", "") + r.get("url", "")]
        if matching:
            csv_resources = matching

    chosen = csv_resources[-1]
    logger.info(f"[QualiteAir] Ressource sélectionnée : {chosen.get('title', '?')}  →  {chosen['url']}")
    return chosen["url"], chosen.get("title", "ATMO")


def _aggregate_to_commune(raw_csv: Path, annee: int) -> list[dict]:
    """
    Agrège le CSV journalier ATMO par commune.

    Colonnes attendues dans le CSV source :
      - code_commune (ou code_insee) : code INSEE 5 chars
      - lib_qualif (ou lib_qualite)  : libellé de la qualité (Bon, Moyen, …)
      - indice_atmo (ou indice)       : valeur numérique 1-10
    """
    logger.info(f"[QualiteAir] Agrégation du CSV {raw_csv.name}…")

    commune_data: dict[str, dict] = {}

    with open(raw_csv, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=",")
        if reader.fieldnames is None:
            raise RuntimeError("[QualiteAir] CSV vide ou sans en-tête")

        headers = [h.lower().strip() for h in reader.fieldnames]

        def col(aliases: list[str]) -> str | None:
            for a in aliases:
                if a in headers:
                    return reader.fieldnames[headers.index(a)]  # type: ignore[index]
            return None

        col_code = col(["code_commune", "code_insee", "codecommune", "code_insee_commune"])
        col_qualif = col(["lib_qualif", "lib_qualite", "libelle_qualif", "qualite", "libqualif"])
        col_indice = col(["indice_atmo", "indice", "valeur_indice", "indice_atmo_prev_jn"])

        if not col_code:
            raise RuntimeError(f"[QualiteAir] Colonne code commune introuvable. Colonnes disponibles : {headers}")

        for row in reader:
            code = (row.get(col_code) or "").strip()
            if not code or len(code) != 5:
                continue

            if code not in commune_data:
                commune_data[code] = {
                    "code_commune": code,
                    "annee": annee,
                    "indice_atmo": [],
                    "nb_jours_bon": 0,
                    "nb_jours_moyen": 0,
                    "nb_jours_degrade": 0,
                    "nb_jours_mauvais": 0,
                    "nb_jours_tres_mauvais": 0,
                    "nb_jours_extremement_mauvais": 0,
                }

            if col_qualif:
                qualif = (row.get(col_qualif) or "").strip().lower()
                col_nb = QUALIF_COLUMN_MAP.get(qualif)
                if col_nb:
                    commune_data[code][col_nb] += 1

            if col_indice:
                try:
                    commune_data[code]["indice_atmo"].append(float(row[col_indice]))
                except (ValueError, TypeError):
                    pass

    results = []
    for entry in commune_data.values():
        indices = entry.pop("indice_atmo")
        entry["indice_atmo"] = round(sum(indices) / len(indices), 2) if indices else None
        results.append(entry)

    logger.info(f"[QualiteAir]  {len(results):,} communes agrégées")
    return results


def run(raw_dir: Path = RAW_DIR, force: bool = False, annee: int | None = None) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / RAW_FILE

    if dest.exists() and not force:
        logger.info(f"[QualiteAir] Déjà présent, ignoré : {dest}  (--force pour écraser)")
        return

    logger.info("=== [QualiteAir] Téléchargement (ATMO France) ===")

    url, title = _get_atmo_csv_url(annee)
    raw_csv = raw_dir / "atmo_raw.csv"
    download_file(url, raw_csv)

    if annee is None:
        match = re.search(r"(20\d{2})", title + url)
        annee = int(match.group(1)) if match else 2024

    results = _aggregate_to_commune(raw_csv, annee)

    with open(dest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)

    raw_csv.unlink(missing_ok=True)
    logger.info(f"[QualiteAir]  → {len(results):,} communes écrites dans {dest}")
