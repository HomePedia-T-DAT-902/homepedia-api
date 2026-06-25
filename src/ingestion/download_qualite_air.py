"""
Téléchargement de l'indice ATMO (qualité de l'air) par commune.

Source : ATMO France / data.gouv.fr
Dataset : Indice ATMO — indices journaliers de qualité de l'air par commune
          https://www.data.gouv.fr/datasets/indice-atmo/

Approche : téléchargement du CSV annuel le plus récent, agrégation par commune.
Sortie   : data/raw/qualite_air/commune_qualite_air.csv

Usage :
    python -m src.ingestion.download_qualite_air
    python -m src.ingestion.download_qualite_air --force
    python -m src.ingestion.download_qualite_air --annee 2024
"""

import argparse
import csv
import logging
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/qualite_air")
DEST_FILE = RAW_DIR / "commune_qualite_air.csv"

# Dataset data.gouv.fr : Indice ATMO France
ATMO_DATASET_ID = "63e7fdc2df4f62671f4e9f8b"

# Mapping libellé qualité → colonne cible (ordre croissant de pollution)
QUALIF_COLUMN_MAP = {
    "bon":                    "nb_jours_bon",
    "moyen":                  "nb_jours_moyen",
    "dégradé":                "nb_jours_degrade",
    "degrade":                "nb_jours_degrade",
    "mauvais":                "nb_jours_mauvais",
    "très mauvais":           "nb_jours_tres_mauvais",
    "tres mauvais":           "nb_jours_tres_mauvais",
    "extrêmement mauvais":    "nb_jours_extremement_mauvais",
    "extremement mauvais":    "nb_jours_extremement_mauvais",
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


def _get_atmo_csv_url(annee: int | None = None) -> tuple[str, str]:
    """Récupère l'URL du CSV ATMO le plus récent (ou pour l'année demandée)."""
    api_url = f"https://www.data.gouv.fr/api/1/datasets/{ATMO_DATASET_ID}/"
    logger.info(f"Interrogation data.gouv.fr : {api_url}")
    r = requests.get(api_url, timeout=30)
    r.raise_for_status()

    resources = r.json().get("resources", [])
    csv_resources = [
        res for res in resources
        if "csv" in res.get("format", "").lower() or res.get("url", "").lower().endswith(".csv")
    ]

    if not csv_resources:
        raise RuntimeError(f"Aucune ressource CSV trouvée pour le dataset {ATMO_DATASET_ID}")

    if annee:
        matching = [r for r in csv_resources if str(annee) in r.get("title", "") + r.get("url", "")]
        if matching:
            csv_resources = matching

    chosen = csv_resources[-1]
    logger.info(f"Ressource sélectionnée : {chosen.get('title', '?')}  →  {chosen['url']}")
    return chosen["url"], chosen.get("title", "ATMO")


def _download_file(url: str, dest: Path, chunk_size: int = 1024 * 1024) -> None:
    logger.info(f"Téléchargement : {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    print(f"\r  {downloaded / total * 100:.1f}%  ({downloaded / 1e6:.1f} MB)", end="", flush=True)
    print()
    logger.info(f"Sauvegardé : {dest}  ({dest.stat().st_size / 1e6:.1f} MB)")


def _aggregate_to_commune(raw_csv: Path, annee: int) -> list[dict]:
    """
    Agrège le CSV journalier ATMO par commune.

    Colonnes attendues dans le CSV source :
      - code_commune (ou code_insee) : code INSEE 5 chars
      - lib_qualif (ou lib_qualite)  : libellé de la qualité (Bon, Moyen, …)
      - indice_atmo (ou indice)       : valeur numérique 1-10

    Retourne une liste de dicts avec les colonnes OUTPUT_COLUMNS.
    """
    logger.info(f"Agrégation du CSV {raw_csv.name}…")

    commune_data: dict[str, dict] = {}

    with open(raw_csv, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=",")
        # Normaliser les noms de colonnes (minuscules, sans accents courants)
        if reader.fieldnames is None:
            raise RuntimeError("CSV vide ou sans en-tête")

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
            raise RuntimeError(f"Colonne code commune introuvable. Colonnes disponibles : {headers}")

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

    # Finaliser : moyenne annuelle de l'indice
    results = []
    for entry in commune_data.values():
        indices = entry.pop("indice_atmo")
        entry["indice_atmo"] = round(sum(indices) / len(indices), 2) if indices else None
        results.append(entry)

    logger.info(f"  {len(results):,} communes agrégées")
    return results


def download_qualite_air(force: bool = False, annee: int | None = None) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if DEST_FILE.exists() and not force:
        logger.info(f"Déjà présent, ignoré : {DEST_FILE}  (--force pour écraser)")
        return

    logger.info("=== Téléchargement qualité de l'air (ATMO France) ===")

    url, title = _get_atmo_csv_url(annee)
    raw_csv = RAW_DIR / "atmo_raw.csv"
    _download_file(url, raw_csv)

    # Déterminer l'année depuis le titre ou le nom de fichier
    if annee is None:
        import re
        match = re.search(r"(20\d{2})", title + url)
        annee = int(match.group(1)) if match else 2024

    results = _aggregate_to_commune(raw_csv, annee)

    with open(DEST_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)

    raw_csv.unlink(missing_ok=True)
    logger.info(f"  → {len(results):,} communes écrites dans {DEST_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Téléchargement indice ATMO par commune.")
    parser.add_argument("--force", action="store_true", help="Re-télécharge même si le fichier existe.")
    parser.add_argument("--annee", type=int, help="Année cible (défaut : la plus récente disponible).")
    args = parser.parse_args()

    download_qualite_air(force=args.force, annee=args.annee)


if __name__ == "__main__":
    main()
