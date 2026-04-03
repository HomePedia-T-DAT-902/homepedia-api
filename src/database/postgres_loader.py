"""
Chargement des données vers PostgreSQL/PostGIS.

Pipeline complet :
  1. Exécute le schéma SQL (CREATE TABLE IF NOT EXISTS)
  2. Charge les régions, départements, communes (Parquet + GeoJSON)
  3. Charge les transactions DVF (Parquet partitionné par année)
  4. Charge les diagnostics DPE (Parquet)
  5. Calcule et charge les price_trends (médiane prix/m² par commune/trimestre)
  6. Charge les parcelles cadastrales (GeoJSON.gz par département)

Sources :
  - data/processed/geo/      → Parquet géo (spark_geo.py)
  - data/processed/dvf/      → Parquet DVF partitionné par annee (spark_dvf.py)
  - data/processed/dpe/      → Parquet DPE diagnostics (spark_dpe.py)
  - data/raw/geo/            → GeoJSON géométries Etalab
  - data/raw/cadastre/       → GeoJSON.gz parcelles Etalab (download_cadastre.py)

Pour les grandes tables (DVF ~10M lignes, DPE ~18M lignes), on utilise
psycopg2 copy_expert (COPY FROM STDIN) — ~10x plus rapide que execute_values.

Usage :
    python -m src.database.postgres_loader
    python -m src.database.postgres_loader --skip-geo --skip-dvf
    python -m src.database.postgres_loader --skip-cadastre
    python -m src.database.postgres_loader --cadastre-dept 75 13 69
    python -m src.database.postgres_loader --processed-dir data/processed --raw-dir data/raw/geo
"""

import argparse
import csv
import io
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "postgres_schema.sql"


def get_connection():
    """Crée une connexion PostgreSQL depuis les variables d'environnement."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ.get("POSTGRES_DB", "homepedia"),
        user=os.environ.get("POSTGRES_USER", "homepedia"),
        password=os.environ.get("POSTGRES_PASSWORD", "homepedia_secret"),
    )


def init_schema(conn) -> None:
    """Exécute le fichier SQL de création du schéma."""
    logger.info(f"Exécution du schéma : {SCHEMA_PATH}")
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.info("Schéma initialisé")


# ── Lecture des données ──────────────────────────────────────────────────────


def read_parquet_dir(parquet_dir: Path) -> pd.DataFrame:
    """
    Lit un dossier Parquet — gère deux cas :
    - Spark sans partition : fichiers *.parquet directement dans le dossier
    - Spark avec partition : sous-dossiers annee=YYYY/ contenant les *.parquet
    """
    files = list(parquet_dir.glob("*.parquet"))
    if files:
        logger.info(f"Lecture Parquet : {files[0]}")
        return pd.read_parquet(files[0])

    # Parquet partitionné (annee=YYYY/part-*.parquet)
    files = list(parquet_dir.glob("**/*.parquet"))
    if not files:
        raise FileNotFoundError(f"Aucun fichier .parquet dans {parquet_dir}")
    logger.info(f"Lecture Parquet partitionné : {len(files)} fichier(s) dans {parquet_dir}")
    return pd.read_parquet(parquet_dir)


def copy_df_to_table(conn, df: pd.DataFrame, table: str, columns: list[str]) -> int:
    """
    Charge un DataFrame en base via COPY FROM STDIN (CSV en mémoire).
    ~10x plus rapide que execute_values pour les grandes tables.
    Retourne le nombre de lignes insérées.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    for row in df[columns].itertuples(index=False):
        writer.writerow(["\\N" if (v is None or (isinstance(v, float) and np.isnan(v))) else v for v in row])
    buf.seek(0)

    with conn.cursor() as cur:
        cur.copy_expert(
            f"COPY {table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')",
            buf,
        )
    conn.commit()
    return len(df)


def read_geojson_geometries(geojson_path: Path) -> dict[str, str]:
    """
    Lit un GeoJSON et retourne un dict {code: geometry_json}.
    Le code est extrait depuis properties.code.
    """
    logger.info(f"Lecture géométries : {geojson_path}")
    with open(geojson_path, encoding="utf-8") as f:
        data = json.load(f)

    geometries = {}
    for feature in data["features"]:
        code = feature["properties"]["code"]
        geom = feature["geometry"]
        # Forcer en MultiPolygon pour cohérence avec le schéma
        if geom["type"] == "Polygon":
            geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
        geometries[code] = json.dumps(geom)

    logger.info(f"  → {len(geometries)} géométries extraites")
    return geometries


# ── Chargement ───────────────────────────────────────────────────────────────


def load_regions(conn, processed_dir: Path, raw_dir: Path) -> None:
    """Charge les régions (attributs + géométries)."""
    logger.info("=== Chargement régions ===")
    df = read_parquet_dir(processed_dir / "regions")
    geoms = read_geojson_geometries(raw_dir / "regions-5m.geojson")

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            code = row["code_region"]
            geom_json = geoms.get(code)
            cur.execute(
                """
                INSERT INTO regions (code_region, nom, geom)
                VALUES (%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                ON CONFLICT (code_region) DO UPDATE SET
                    nom = EXCLUDED.nom,
                    geom = EXCLUDED.geom
                """,
                (code, row["nom"], geom_json),
            )
    conn.commit()
    logger.info(f"  → {len(df)} régions chargées")


def load_departements(conn, processed_dir: Path, raw_dir: Path) -> None:
    """Charge les départements (attributs + géométries)."""
    logger.info("=== Chargement départements ===")
    df = read_parquet_dir(processed_dir / "departements")
    geoms = read_geojson_geometries(raw_dir / "departements-5m.geojson")

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            code = row["code_departement"]
            geom_json = geoms.get(code)
            cur.execute(
                """
                INSERT INTO departements (code_departement, nom, code_region, geom)
                VALUES (%s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                ON CONFLICT (code_departement) DO UPDATE SET
                    nom = EXCLUDED.nom,
                    code_region = EXCLUDED.code_region,
                    geom = EXCLUDED.geom
                """,
                (code, row["nom"], row["code_region"], geom_json),
            )
    conn.commit()
    logger.info(f"  → {len(df)} départements chargés")


def load_communes(conn, processed_dir: Path, raw_dir: Path) -> None:
    """
    Charge les communes (attributs Parquet + géométries GeoJSON).
    - geom : contours 5m (précis)
    - geom_simplified : contours 50m (carte zoomée)
    """
    logger.info("=== Chargement communes ===")
    df = read_parquet_dir(processed_dir / "communes")
    # Padder les codes région (ex: "1" → "01") pour correspondre à la table regions
    if "code_region" in df.columns:
        df["code_region"] = df["code_region"].astype(str).str.zfill(2)
    geoms_5m = read_geojson_geometries(raw_dir / "communes-5m.geojson")
    geoms_50m = read_geojson_geometries(raw_dir / "communes-50m.geojson")

    loaded = 0
    skipped = 0

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            code = row["code_commune"]
            geom_5m = geoms_5m.get(code)
            geom_50m = geoms_50m.get(code)

            if not geom_5m:
                skipped += 1
                continue

            cur.execute(
                """
                INSERT INTO communes (
                    code_commune, nom, code_departement, code_region,
                    code_postal, population, superficie, densite,
                    latitude, longitude, geom, geom_simplified
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
                )
                ON CONFLICT (code_commune) DO UPDATE SET
                    nom = EXCLUDED.nom,
                    code_departement = EXCLUDED.code_departement,
                    code_region = EXCLUDED.code_region,
                    code_postal = EXCLUDED.code_postal,
                    population = EXCLUDED.population,
                    superficie = EXCLUDED.superficie,
                    densite = EXCLUDED.densite,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    geom = EXCLUDED.geom,
                    geom_simplified = EXCLUDED.geom_simplified
                """,
                (
                    code,
                    row["nom"],
                    row.get("code_departement"),
                    row.get("code_region"),
                    row.get("code_postal"),
                    int(row["population"]) if pd.notna(row.get("population")) else None,
                    float(row["superficie"]) if pd.notna(row.get("superficie")) else None,
                    float(row["densite"]) if pd.notna(row.get("densite")) else None,
                    float(row["latitude"]) if pd.notna(row.get("latitude")) else None,
                    float(row["longitude"]) if pd.notna(row.get("longitude")) else None,
                    geom_5m,
                    geom_50m,
                ),
            )

            loaded += 1
            if loaded % 5000 == 0:
                conn.commit()
                logger.info(f"  → {loaded} communes chargées...")

    conn.commit()
    logger.info(f"  → {loaded} communes chargées, {skipped} ignorées (pas de géométrie)")


# ── DVF ──────────────────────────────────────────────────────────────────────


def load_dvf_transactions(conn, processed_dir: Path, batch_size: int = 100_000) -> None:
    """
    Charge les transactions DVF depuis le Parquet partitionné (spark_dvf.py).
    Utilise COPY FROM STDIN par batch pour gérer les ~10M lignes.

    Vide la table avant chargement (mode overwrite — pas d'UPSERT sur DVF
    car il n'y a pas de clé naturelle stable sur SERIAL).
    Pour un chargement incrémental, filtrer le Parquet sur annee >= X en amont.
    """
    logger.info("=== Chargement DVF transactions ===")
    dvf_dir = processed_dir / "dvf"
    if not dvf_dir.exists():
        logger.warning(f"Dossier DVF absent : {dvf_dir} — chargement ignoré")
        return

    df = read_parquet_dir(dvf_dir)
    logger.info(f"  {len(df):,} transactions lues")

    # Vider la table avant rechargement complet
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE dvf_transactions RESTART IDENTITY CASCADE")
    conn.commit()
    logger.info("  Table dvf_transactions vidée")

    columns = [
        "id_mutation", "code_commune", "date_mutation", "nature_mutation",
        "type_local", "valeur_fonciere", "surface_reelle_bati",
        "nombre_pieces_principales", "surface_terrain", "prix_m2",
        "longitude", "latitude",
    ]
    # Renommer nombre_pieces_principales → nb_pieces (nom de la colonne en DB)
    df = df.rename(columns={"nombre_pieces_principales": "nb_pieces"})
    columns[7] = "nb_pieces"

    df["nb_pieces"] = pd.to_numeric(df["nb_pieces"], errors="coerce")
    df["nb_pieces"] = df["nb_pieces"].round().astype("Int64")

    # Convertir date en string ISO pour COPY
    df["date_mutation"] = pd.to_datetime(df["date_mutation"]).dt.strftime("%Y-%m-%d")

    total = 0
    for start in range(0, len(df), batch_size):
        batch = df.iloc[start: start + batch_size]
        copy_df_to_table(conn, batch, "dvf_transactions", columns)
        total += len(batch)
        logger.info(f"  → {total:,} / {len(df):,} lignes chargées")

    # Créer la colonne geom depuis longitude/latitude pour les transactions géolocalisées
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE dvf_transactions
            SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
            WHERE longitude IS NOT NULL AND latitude IS NOT NULL
        """)
    conn.commit()
    logger.info(f"  → Géométries mises à jour")
    logger.info(f"  → {total:,} transactions DVF chargées")


# ── DPE ──────────────────────────────────────────────────────────────────────


def load_dpe_diagnostics(conn, processed_dir: Path, batch_size: int = 200_000) -> None:
    """
    Charge les diagnostics DPE individuels depuis le Parquet (spark_dpe.py).
    ~18M lignes — chargement par batch via COPY FROM STDIN.
    """
    logger.info("=== Chargement DPE diagnostics ===")
    dpe_dir = processed_dir / "dpe" / "diagnostics"
    if not dpe_dir.exists():
        logger.warning(f"Dossier DPE absent : {dpe_dir} — chargement ignoré")
        return

    df = read_parquet_dir(dpe_dir)
    logger.info(f"  {len(df):,} diagnostics lus")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE dpe_diagnostics RESTART IDENTITY CASCADE")
    conn.commit()

    df["date_diagnostic"] = pd.to_datetime(df["date_diagnostic"]).dt.strftime("%Y-%m-%d")

    columns = ["code_commune", "date_diagnostic", "classe_energie", "consommation_moyenne", "source"]

    total = 0
    for start in range(0, len(df), batch_size):
        batch = df.iloc[start: start + batch_size]
        copy_df_to_table(conn, batch, "dpe_diagnostics", columns)
        total += len(batch)
        logger.info(f"  → {total:,} / {len(df):,} lignes chargées")

    logger.info(f"  → {total:,} diagnostics DPE chargés")


# ── BPE ──────────────────────────────────────────────────────────────────────


def load_bpe_stats(conn, processed_dir: Path) -> None:
    """
    Charge les statistiques BPE par commune depuis le Parquet (spark_bpe.py).
    UPSERT sur code_commune (clé primaire).
    """
    logger.info("=== Chargement BPE commune_stats ===")
    bpe_dir = processed_dir / "bpe" / "commune_stats"
    if not bpe_dir.exists():
        logger.warning(f"Dossier BPE absent : {bpe_dir} — chargement ignoré")
        return

    df = read_parquet_dir(bpe_dir)
    logger.info(f"  {len(df):,} communes lues")

    columns = [
        "code_commune", "nb_equipements_total",
        "nb_a", "nb_b", "nb_c", "nb_d", "nb_e", "nb_f",
        "nb_maternelles", "nb_primaires", "nb_creches", "nb_colleges", "nb_lycees",
        "nb_medecins", "nb_pharmacies", "nb_urgences",
        "nb_supermarches", "nb_hypermarches", "nb_gares",
    ]
    # S'assurer que toutes les colonnes numériques sont bien des int (Spark → Int64 nullable)
    for col in columns[1:]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    upsert_sql = f"""
        INSERT INTO bpe_commune_stats ({', '.join(columns)})
        VALUES %s
        ON CONFLICT (code_commune) DO UPDATE SET
            {', '.join(f'{c} = EXCLUDED.{c}' for c in columns[1:])}
    """

    rows = [
        tuple(None if pd.isna(row[c]) else int(row[c]) if c != "code_commune" else row[c] for c in columns)
        for _, row in df[columns].iterrows()
    ]

    batch_size = 10_000
    total = 0
    with conn.cursor() as cur:
        for start in range(0, len(rows), batch_size):
            execute_values(cur, upsert_sql, rows[start: start + batch_size])
            total += min(batch_size, len(rows) - start)
        conn.commit()

    logger.info(f"  → {total:,} communes BPE chargées (UPSERT)")


# ── Price trends ──────────────────────────────────────────────────────────────


def compute_and_load_price_trends(conn, processed_dir: Path) -> None:
    """
    Calcule et charge la table price_trends depuis le Parquet DVF.

    price_trends = médiane prix/m² par (code_commune, annee, trimestre, type_local)
    + nombre de transactions
    + variation annuelle en % (YoY sur le même trimestre de l'année précédente)

    Utilise UPSERT (ON CONFLICT DO UPDATE) car c'est une table analytique
    avec une clé naturelle stable.
    """
    logger.info("=== Calcul + chargement price_trends ===")
    dvf_dir = processed_dir / "dvf"
    if not dvf_dir.exists():
        logger.warning(f"Dossier DVF absent : {dvf_dir} — price_trends ignoré")
        return

    df = read_parquet_dir(dvf_dir)
    df = df[df["prix_m2"].notna() & df["date_mutation"].notna()].copy()

    df["date_mutation"] = pd.to_datetime(df["date_mutation"])
    df["annee"] = df["date_mutation"].dt.year.astype(int)
    df["trimestre"] = df["date_mutation"].dt.quarter.astype(int)

    logger.info("  Calcul médiane prix/m² par commune/trimestre/type_local...")
    trends = (
        df.groupby(["code_commune", "annee", "trimestre", "type_local"])
        .agg(
            prix_median_m2=("prix_m2", "median"),
            nb_transactions=("prix_m2", "count"),
        )
        .reset_index()
    )
    trends["prix_median_m2"] = trends["prix_median_m2"].round(2)

    # Variation annuelle (YoY) — même trimestre, année précédente
    logger.info("  Calcul variation annuelle (YoY)...")
    prev = trends.copy()
    prev["annee"] = prev["annee"] + 1
    prev = prev.rename(columns={"prix_median_m2": "prix_median_m2_prev"})

    trends = trends.merge(
        prev[["code_commune", "annee", "trimestre", "type_local", "prix_median_m2_prev"]],
        on=["code_commune", "annee", "trimestre", "type_local"],
        how="left",
    )
    trends["variation_annuelle_pct"] = (
        (trends["prix_median_m2"] - trends["prix_median_m2_prev"])
        / trends["prix_median_m2_prev"]
        * 100
    ).round(2)
    trends = trends.drop(columns=["prix_median_m2_prev"])

    logger.info(f"  {len(trends):,} entrées price_trends calculées")

    # UPSERT par batch
    upsert_sql = """
        INSERT INTO price_trends
            (code_commune, annee, trimestre, type_local, prix_median_m2, nb_transactions, variation_annuelle_pct)
        VALUES %s
        ON CONFLICT (code_commune, annee, trimestre, type_local) DO UPDATE SET
            prix_median_m2 = EXCLUDED.prix_median_m2,
            nb_transactions = EXCLUDED.nb_transactions,
            variation_annuelle_pct = EXCLUDED.variation_annuelle_pct
    """

    batch_size = 10_000
    total = 0
    with conn.cursor() as cur:
        for start in range(0, len(trends), batch_size):
            batch = trends.iloc[start: start + batch_size]
            rows = [
                (
                    row.code_commune, int(row.annee), int(row.trimestre), row.type_local,
                    None if np.isnan(row.prix_median_m2) else float(row.prix_median_m2),
                    int(row.nb_transactions),
                    None if np.isnan(row.variation_annuelle_pct) else float(row.variation_annuelle_pct),
                )
                for row in batch.itertuples()
            ]
            execute_values(cur, upsert_sql, rows)
            total += len(batch)
        conn.commit()

    logger.info(f"  → {total:,} entrées price_trends chargées (UPSERT)")


# ── Cadastre ──────────────────────────────────────────────────────────────────


def load_cadastre_parcelles(conn, cadastre_raw_dir: Path, depts_filter: list[str] | None = None) -> None:
    """
    Charge les parcelles cadastrales depuis les GeoJSON.gz par département.
    Délègue à load_cadastre.load_dept (streaming ijson + batch COPY).

    cadastre_raw_dir : dossier contenant les parcelles_*.geojson.gz
    depts_filter     : liste de codes dept à charger (None = tous les fichiers présents)
    """
    from src.database.load_cadastre import load_dept

    logger.info("=== Chargement cadastre parcelles ===")

    if not cadastre_raw_dir.exists():
        logger.warning(f"Dossier cadastre absent : {cadastre_raw_dir} — chargement ignoré")
        return

    gz_files = sorted(cadastre_raw_dir.glob("parcelles_*.geojson.gz"))
    if not gz_files:
        logger.warning(f"Aucun fichier GeoJSON.gz dans {cadastre_raw_dir} — chargement ignoré")
        return

    if depts_filter:
        gz_files = [f for f in gz_files if any(f.stem == f"parcelles_{d}" for d in depts_filter)]

    logger.info(f"  {len(gz_files)} département(s) à charger")

    total = 0
    errors = []
    for i, gz_path in enumerate(gz_files, 1):
        dept = gz_path.stem.replace("parcelles_", "")
        logger.info(f"[{i}/{len(gz_files)}] Département {dept}")
        try:
            total += load_dept(conn, gz_path)
        except Exception as e:
            logger.error(f"  [{dept}] ERREUR : {e}")
            conn.rollback()
            errors.append(dept)

    logger.info(f"  → {total:,} parcelles cadastrales chargées")
    if errors:
        logger.warning(f"  Départements en erreur : {errors}")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Chargement des données en base PostgreSQL.")
    parser.add_argument(
        "--processed-dir", default="data/processed",
        help="Dossier racine des Parquet traités (sous-dossiers geo/, dvf/, dpe/).",
    )
    parser.add_argument(
        "--raw-dir", default="data/raw/geo",
        help="Dossier des GeoJSON bruts (pour géométries communes/depts/régions).",
    )
    parser.add_argument(
        "--cadastre-dir", default="data/raw/cadastre",
        help="Dossier des GeoJSON.gz cadastre (parcelles_*.geojson.gz).",
    )
    parser.add_argument("--skip-geo", action="store_true", help="Ne pas charger les données géo.")
    parser.add_argument("--skip-dvf", action="store_true", help="Ne pas charger DVF.")
    parser.add_argument("--skip-dpe", action="store_true", help="Ne pas charger DPE.")
    parser.add_argument("--skip-bpe", action="store_true", help="Ne pas charger BPE.")
    parser.add_argument("--skip-trends", action="store_true", help="Ne pas calculer price_trends.")
    parser.add_argument("--skip-cadastre", action="store_true", help="Ne pas charger les parcelles cadastrales.")
    parser.add_argument(
        "--cadastre-dept", nargs="+", metavar="DEPT",
        help="Restreindre le chargement cadastre à ces départements (ex: 75 13 69).",
    )
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir)
    raw_dir = Path(args.raw_dir)

    conn = get_connection()
    try:
        init_schema(conn)

        if not args.skip_geo:
            geo_processed = processed_dir / "geo"
            load_regions(conn, geo_processed, raw_dir)
            load_departements(conn, geo_processed, raw_dir)
            load_communes(conn, geo_processed, raw_dir)

        if not args.skip_dvf:
            load_dvf_transactions(conn, processed_dir)

        if not args.skip_dpe:
            load_dpe_diagnostics(conn, processed_dir)

        if not args.skip_bpe:
            load_bpe_stats(conn, processed_dir)

        if not args.skip_trends:
            compute_and_load_price_trends(conn, processed_dir)

        if not args.skip_cadastre:
            load_cadastre_parcelles(conn, Path(args.cadastre_dir), depts_filter=args.cadastre_dept)

        logger.info("=== Chargement complet terminé ===")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
