"""
Téléchargement des données DPE — Diagnostics de Performance Énergétique (P1-3).

Les DPE ne sont PAS téléchargeables en un seul fichier sur data.gouv.fr.
Ils sont hébergés sur la plateforme ADEME data-fair, accessibles via une API paginée.

2 sources :
- DPE nouveau (post-juillet 2021) : API ADEME, ~14M lignes, dataset meg-83tjwtg8dyz4vv7h1dqe
- DPE ancien  (pré-juillet 2021)  : API ADEME, ~10.7M lignes, dataset dpe-france
    Filtres obligatoires : dpe_vierge=0 ET est_efface=0

Volume total : ~24M lignes — téléchargement paginé (10 000 lignes/requête)
Note : le téléchargement est long (~2h pour le nouveau DPE). Lancer en fond ou sur un serveur.

Usage :
    python -m src.ingestion.download_dpe                  # télécharge les deux sources
    python -m src.ingestion.download_dpe --source nouveau # DPE post-2021 uniquement
    python -m src.ingestion.download_dpe --source ancien  # DPE pré-2021 uniquement
    python -m src.ingestion.download_dpe --force          # re-télécharge tout
"""

import argparse
import csv
import gzip
import logging
import re
import shutil
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/dpe")

# ── API ADEME data-fair ───────────────────────────────────────────────────────
# Les DPE sont hébergés sur la plateforme ADEME (pas data.gouv.fr).
ADEME_API_BASE = "https://data.ademe.fr/data-fair/api/v1/datasets"
DPE_NOUVEAU_DATASET_ID = "meg-83tjwtg8dyz4vv7h1dqe"  # ~14M lignes post-2021
DPE_ANCIEN_DATASET_ID = "dpe-france"  # ~10.7M lignes pré-2021

# Colonnes utiles seulement (le dataset en contient ~200)
DPE_NOUVEAU_COLS = "code_insee_ban,date_etablissement_dpe,etiquette_dpe,conso_5_usages_par_m2_ef"
DPE_ANCIEN_COLS = "code_insee_commune_actualise,date_etablissement_dpe,classe_consommation_energie,consommation_energie"

# Taille de page (max autorisé par l'API ADEME)
ADEME_PAGE_SIZE = 10_000

# Noms de fichiers de sortie
DPE_NOUVEAU_DEST = "dpe_nouveau.csv"
DPE_ANCIEN_DEST = "dpe_ancien.csv"
DPE_ANCIEN_SQL_DEST = "dpe_ancien.sql.gz"


# ── Utilitaires ───────────────────────────────────────────────────────────────


def download_file(url: str, dest: Path, chunk_size: int = 1024 * 1024) -> None:
    """Télécharge un fichier vers dest avec affichage de la progression."""
    logger.info(f"Téléchargement : {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(
                        f"\r  {pct:.1f}%  ({downloaded / 1e6:.0f} MB / {total / 1e6:.0f} MB)",
                        end="",
                        flush=True,
                    )
        print()

    logger.info(f"Sauvegardé : {dest}  ({dest.stat().st_size / 1e6:.0f} MB)")


def decompress_gz(gz_path: Path, dest_path: Path) -> None:
    """Décompresse un fichier .gz vers dest_path puis supprime le .gz."""
    logger.info(f"Décompression : {gz_path.name} → {dest_path.name}")
    with gzip.open(gz_path, "rb") as f_in, open(dest_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    gz_path.unlink()
    logger.info(f"Extrait : {dest_path}  ({dest_path.stat().st_size / 1e6:.0f} MB)")


def get_datagouv_resource(dataset_id: str, format_hints: list[str]) -> tuple[str, str]:
    """
    Récupère l'URL + nom de la ressource principale d'un dataset data.gouv.fr.
    Cherche parmi format_hints dans l'ordre (ex: ['csv', 'gz', 'sql']).
    Retourne (url, title).
    """
    api_url = f"https://www.data.gouv.fr/api/1/datasets/{dataset_id}/"
    logger.info(f"API data.gouv.fr : {api_url}")
    r = requests.get(api_url, timeout=30)
    r.raise_for_status()

    resources = r.json().get("resources", [])
    if not resources:
        raise RuntimeError(f"Aucune ressource pour le dataset {dataset_id}")

    for hint in format_hints:
        matching = [
            res
            for res in resources
            if hint.lower() in res.get("format", "").lower() or hint.lower() in res.get("url", "").lower()
        ]
        if matching:
            chosen = matching[-1]
            return chosen["url"], chosen.get("title", hint)

    # Fallback : première ressource
    chosen = resources[0]
    return chosen["url"], chosen.get("title", "?")


# ── Conversion dump MySQL → CSV ───────────────────────────────────────────────

# Regex pour extraire les valeurs d'un INSERT INTO ... VALUES (...), (...);
# Gère les chaînes avec virgules et apostrophes échappées.
_INSERT_RE = re.compile(r"INSERT INTO `\w+` VALUES\s*(.+);", re.DOTALL)
_ROW_RE = re.compile(r"\(([^)]*(?:'[^']*'[^)]*)*)\)")


def _parse_sql_value(v: str) -> str:
    """Nettoie une valeur SQL : retire les quotes, gère NULL et échappements."""
    v = v.strip()
    if v.upper() == "NULL":
        return ""
    if v.startswith("'") and v.endswith("'"):
        v = v[1:-1]
        v = v.replace("\\'", "'").replace("\\\\", "\\").replace("\\n", "\n")
    return v


def _extract_column_names(sql_gz_path: Path, table_name_hint: str = "") -> list[str]:
    """
    Tente d'extraire les noms de colonnes depuis le CREATE TABLE du dump.
    Retourne une liste vide si non trouvé (les colonnes seront numérotées col_0, col_1…).
    """
    col_re = re.compile(r"^\s+`(\w+)`", re.MULTILINE)
    create_re = re.compile(r"CREATE TABLE `\w+`\s*\((.+?)\);", re.DOTALL)

    try:
        with gzip.open(sql_gz_path, "rt", encoding="utf-8", errors="replace") as f:
            content = ""
            for i, line in enumerate(f):
                content += line
                if i > 5000:  # les CREATE TABLE sont en début de dump
                    break

        match = create_re.search(content)
        if match:
            return col_re.findall(match.group(1))
    except Exception as e:
        logger.warning(f"Impossible d'extraire les colonnes du dump : {e}")

    return []


def convert_sql_dump_to_csv(sql_gz_path: Path, csv_dest: Path, encoding: str = "utf-8") -> None:
    """
    Convertit un dump MySQL (.sql.gz) en CSV.
    Parse les INSERT INTO … VALUES ligne par ligne pour éviter de tout charger en mémoire.
    """
    logger.info(f"Conversion dump MySQL → CSV : {sql_gz_path.name} → {csv_dest.name}")

    columns = _extract_column_names(sql_gz_path)
    if columns:
        logger.info(f"  Colonnes détectées ({len(columns)}) : {columns[:5]} …")
    else:
        logger.info("  Colonnes non détectées → en-têtes génériques (col_0, col_1 …)")

    row_count = 0
    writer = None
    out_file = None

    try:
        out_file = open(csv_dest, "w", newline="", encoding="utf-8")
        writer = None  # initialisé au premier INSERT pour connaître le nb de colonnes

        with gzip.open(sql_gz_path, "rt", encoding=encoding, errors="replace") as f:
            buffer = ""
            for raw_line in f:
                line = raw_line.strip()

                # Accumuler les lignes multi-lignes si nécessaire
                buffer += " " + line
                if not line.endswith(";"):
                    continue

                # Chercher INSERT INTO … VALUES
                m = _INSERT_RE.search(buffer)
                buffer = ""
                if not m:
                    continue

                values_block = m.group(1)
                for row_match in _ROW_RE.finditer(values_block):
                    raw_vals = row_match.group(1)
                    # Séparer les valeurs en respectant les chaînes SQL
                    vals = [_parse_sql_value(v) for v in _split_sql_values(raw_vals)]

                    if writer is None:
                        if not columns:
                            columns = [f"col_{i}" for i in range(len(vals))]
                        writer = csv.writer(out_file)
                        writer.writerow(columns)

                    writer.writerow(vals)
                    row_count += 1
                    if row_count % 500_000 == 0:
                        logger.info(f"  … {row_count:,} lignes converties")

    finally:
        if out_file:
            out_file.close()

    logger.info(f"Conversion terminée : {row_count:,} lignes → {csv_dest}  ({csv_dest.stat().st_size / 1e6:.0f} MB)")


def _split_sql_values(values_str: str) -> list[str]:
    """
    Divise une chaîne de valeurs SQL en respectant les chaînes entre guillemets.
    Ex : "1,'foo,bar','baz'" → ["1", "'foo,bar'", "'baz'"]
    """
    result = []
    current = ""
    in_string = False
    i = 0
    while i < len(values_str):
        ch = values_str[i]
        if ch == "'" and not in_string:
            in_string = True
            current += ch
        elif ch == "'" and in_string:
            # Apostrophe échappée : ''
            if i + 1 < len(values_str) and values_str[i + 1] == "'":
                current += "''"
                i += 1
            # Backslash-quote : \'
            elif current.endswith("\\"):
                current += ch
            else:
                in_string = False
                current += ch
        elif ch == "," and not in_string:
            result.append(current.strip())
            current = ""
        else:
            current += ch
        i += 1

    if current.strip():
        result.append(current.strip())

    return result


# ── Sources ───────────────────────────────────────────────────────────────────


def _download_ademe_paginated(dataset_id: str, select_cols: str, dest: Path, filters: str = "") -> None:
    """
    Télécharge un dataset ADEME data-fair en mode paginé (cursor-based).
    Écrit directement en CSV au fur et à mesure pour ne pas tout charger en mémoire.

    L'API ADEME utilise un paramètre `after` (valeur du curseur de la dernière ligne)
    pour la pagination : GET /lines?size=N&after=X&select=col1,col2
    """
    base_url = f"{ADEME_API_BASE}/{dataset_id}/lines"
    params = {
        "size": ADEME_PAGE_SIZE,
        "select": select_cols,
    }
    if filters:
        params["qs"] = filters

    total_count = None
    written = 0
    after = None
    header_written = False

    with open(dest, "w", newline="", encoding="utf-8") as out_f:
        writer = None

        while True:
            if after:
                params["after"] = after

            r = requests.get(base_url, params=params, timeout=60)
            r.raise_for_status()
            data = r.json()

            if total_count is None:
                total_count = data.get("total", "?")
                logger.info(
                    f"  Total ADEME : {total_count:,} lignes"
                    if isinstance(total_count, int)
                    else f"  Total : {total_count}"
                )

            results = data.get("results", [])
            if not results:
                break

            # Écrire l'en-tête au premier batch
            if not header_written:
                writer = csv.DictWriter(out_f, fieldnames=list(results[0].keys()))
                writer.writeheader()
                header_written = True

            writer.writerows(results)
            written += len(results)

            # Curseur pour la page suivante
            # data["next"] est une URL complète — extraire le paramètre "after"
            import urllib.parse

            next_url = data.get("next")
            if next_url:
                qs = urllib.parse.urlparse(next_url).query
                after = urllib.parse.parse_qs(qs).get("after", [None])[0]
            else:
                after = None

            if written % 500_000 < ADEME_PAGE_SIZE:
                pct = f" ({written / total_count * 100:.0f}%)" if isinstance(total_count, int) and total_count else ""
                logger.info(f"  → {written:,} lignes écrites{pct}")

            if not after:
                break

    logger.info(f"  Terminé : {written:,} lignes → {dest}  ({dest.stat().st_size / 1e6:.0f} MB)")


def download_dpe_nouveau(force: bool = False) -> None:
    """DPE post-juillet 2021 — API ADEME paginée (~14M lignes)."""
    logger.info("=== [1/2] DPE nouveau (post-juillet 2021) — API ADEME ===")

    dest = RAW_DIR / DPE_NOUVEAU_DEST
    if dest.exists() and not force:
        logger.info(f"Déjà présent, ignoré : {DPE_NOUVEAU_DEST}  (--force pour écraser)")
        return

    logger.info(f"  Dataset ADEME : {DPE_NOUVEAU_DATASET_ID}")
    logger.info("  Note : ~14M lignes, téléchargement long (~1-2h selon débit).")
    _download_ademe_paginated(DPE_NOUVEAU_DATASET_ID, DPE_NOUVEAU_COLS, dest)


def download_dpe_ancien(force: bool = False) -> None:
    """DPE pré-juillet 2021 — API ADEME paginée (~10.7M lignes, filtre vierge/effacé)."""
    logger.info("=== [2/2] DPE ancien (pré-juillet 2021) — API ADEME ===")

    dest = RAW_DIR / DPE_ANCIEN_DEST
    if dest.exists() and not force:
        logger.info(f"Déjà présent, ignoré : {DPE_ANCIEN_DEST}  (--force pour écraser)")
        return

    logger.info(f"  Dataset ADEME : {DPE_ANCIEN_DATASET_ID}")
    _download_ademe_paginated(DPE_ANCIEN_DATASET_ID, DPE_ANCIEN_COLS, dest)


def _is_sql_dump(path: Path) -> bool:
    """Vérifie si un fichier .gz contient un dump MySQL (commence par -- MySQL dump)."""
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            header = f.read(200)
        return "MySQL" in header or "CREATE TABLE" in header or "INSERT INTO" in header
    except Exception:
        return False


# ── Entrée ────────────────────────────────────────────────────────────────────

SOURCES = {
    "nouveau": download_dpe_nouveau,
    "ancien": download_dpe_ancien,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Téléchargement des données DPE (2 sources).")
    parser.add_argument(
        "--source",
        choices=list(SOURCES.keys()),
        help="nouveau = post-2021 CSV | ancien = pré-2021 dump MySQL (défaut : les deux).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-télécharge même si le fichier existe déjà.",
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Dossier de sortie : {RAW_DIR.resolve()}")

    if args.source:
        SOURCES[args.source](force=args.force)
    else:
        for fn in SOURCES.values():
            fn(force=args.force)

    logger.info("=== Téléchargement DPE terminé ===")
    logger.info("Fichiers disponibles :")
    for f in sorted(RAW_DIR.iterdir()):
        if f.is_file():
            logger.info(f"  {f.name}  ({f.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
