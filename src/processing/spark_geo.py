"""
Traitement PySpark des tables de référence géographique (communes, départements, régions).

Ce script traite les ATTRIBUTS des entités administratives françaises :
codes INSEE, noms, hiérarchie, population, superficie, densité, coordonnées.

Il ne traite PAS les géométries PostGIS (contours GeoJSON) — celles-ci seront
chargées directement depuis les GeoJSON Etalab dans load_geo.py via ST_GeomFromGeoJSON.

Sources (data/raw/geo/) :
  - communes-france-2025.csv      → attributs communes (nom, codes, coords, superficie)
  - population-municipale.xlsx    → population 2023 (p23_pop), source INSEE
  - departements-5m.geojson       → attributs départements (properties uniquement, sans géométrie)
  - regions-5m.geojson            → attributs régions (properties uniquement, sans géométrie)

Sorties (data/processed/geo/) :
  - communes/       → 34 935 lignes
  - departements/   → 109 lignes (métropole + DOM-TOM)
  - regions/        → 26 lignes (métropole + DOM-TOM)

Usage :
    docker-compose run --rm processing python -m src.processing.spark_geo
    docker-compose run --rm processing python -m src.processing.spark_geo --raw-dir data/raw/geo --out-dir data/processed/geo
"""

import argparse
import logging
from pathlib import Path

import json
import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType

from src.processing.spark_utils import build_local_friendly_spark_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── Schémas explicites ────────────────────────────────────────────────────────
# Déclarer les schémas évite que Spark infère les types (plus lent + risque d'erreur
# sur les codes INSEE qui commencent par 0, ex: "01001" lu comme entier 1001).

COMMUNES_CSV_SCHEMA = StructType(
    [
        StructField("code_insee", StringType(), True),
        StructField("nom_standard", StringType(), True),
        StructField("dep_code", StringType(), True),
        StructField("reg_code", StringType(), True),
        StructField("code_postal", StringType(), True),
        StructField("superficie_km2", DoubleType(), True),
        StructField("densite", DoubleType(), True),  # sera recalculée
        StructField("latitude_centre", DoubleType(), True),
        StructField("longitude_centre", DoubleType(), True),
    ]
)

POPULATION_SCHEMA = StructType(
    [
        StructField("codgeo", StringType(), True),
        StructField("p23_pop", DoubleType(), True),
    ]
)


def build_spark_session(app_name: str = "spark_geo") -> SparkSession:
    """Crée une SparkSession adaptée au dev local et au cluster."""
    return build_local_friendly_spark_session(app_name, driver_memory="2g", shuffle_partitions="100")


# ── Lectures ──────────────────────────────────────────────────────────────────


def read_communes_csv(spark: SparkSession, raw_dir: Path) -> DataFrame:
    """Lit le CSV attributs communes et sélectionne les colonnes utiles."""
    path = str(raw_dir / "communes-france-2025.csv")
    logger.info(f"Lecture : {path}")

    df = (
        spark.read.option("header", "true")
        .option("encoding", "UTF-8")
        .option("sep", ",")
        # On laisse Spark inférer les types sauf pour les codes (StringType imposé via select)
        .csv(path)
    )

    # Sélection + renommage pour coller au schéma DB
    df = df.select(
        F.col("code_insee").cast(StringType()).alias("code_commune"),
        F.col("nom_standard").alias("nom"),
        F.col("dep_code").alias("code_departement"),
        F.col("reg_code").alias("code_region"),
        F.col("code_postal"),
        F.col("superficie_km2").cast(DoubleType()).alias("superficie"),
        F.col("latitude_centre").cast(DoubleType()).alias("latitude"),
        F.col("longitude_centre").cast(DoubleType()).alias("longitude"),
    )

    logger.info(f"Communes CSV : {df.count()} lignes")
    return df


def read_population_xlsx(spark: SparkSession, raw_dir: Path) -> DataFrame:
    """
    Lit le fichier XLSX population via pandas puis convertit en Spark DataFrame.
    PySpark ne lit pas les XLSX nativement — pandas sert de pont.
    """
    path = raw_dir / "population-municipale.xlsx"
    logger.info(f"Lecture (pandas → Spark) : {path}")

    # pandas lit le XLSX
    pdf = pd.read_excel(path, dtype={"codgeo": str})

    # On garde uniquement les colonnes utiles
    pdf = pdf[["codgeo", "p23_pop"]].dropna(subset=["codgeo"])
    pdf["codgeo"] = pdf["codgeo"].str.zfill(5)  # s'assure que le code est sur 5 chars
    pdf["p23_pop"] = pd.to_numeric(pdf["p23_pop"], errors="coerce")

    # Conversion en Spark DataFrame
    df = spark.createDataFrame(pdf, schema=POPULATION_SCHEMA)

    logger.info(f"Population XLSX : {df.count()} lignes")
    return df


def read_geojson_properties(spark: SparkSession, path: Path) -> DataFrame:
    """
    Extrait uniquement les properties d'un GeoJSON FeatureCollection.

    On utilise le module json de Python (pas Spark) pour parser le fichier —
    les GeoJSON contiennent des géométries massives (milliers de coordonnées)
    que Spark parserait inutilement. On extrait juste les properties (quelques
    colonnes texte/nombre) puis on crée un Spark DataFrame depuis cette liste.

    Structure GeoJSON :
        { "features": [ { "properties": {...}, "geometry": {...} }, ... ] }
    """
    logger.info(f"Lecture GeoJSON (properties uniquement) : {path}")

    with open(path, encoding="utf-8") as f:
        features = json.load(f)["features"]

    # Extrait uniquement les properties — geometry ignorée
    props = [feature["properties"] for feature in features]

    # Convertit en Spark DataFrame via pandas (bridge standard)
    pdf = pd.DataFrame(props)
    df = spark.createDataFrame(pdf)

    logger.info(f"  → {df.count()} features extraites")
    return df


# ── Transformations ───────────────────────────────────────────────────────────


def build_communes(
    communes_df: DataFrame,
    population_df: DataFrame,
) -> DataFrame:
    """
    Jointure communes + population, calcul de la densité.

    - left join pour garder toutes les communes même si la population manque
    - densite recalculée à partir de p23_pop (plus récent que la densité du CSV)
    """
    df = communes_df.join(
        population_df.withColumnRenamed("codgeo", "code_commune"),
        on="code_commune",
        how="left",
    )

    # Population en entier, densité recalculée
    df = df.withColumn("population", F.col("p23_pop").cast(IntegerType()))
    df = df.withColumn(
        "densite",
        F.when(
            F.col("superficie") > 0,
            F.round(F.col("population") / F.col("superficie"), 2),
        ).otherwise(None),
    )
    df = df.drop("p23_pop")

    return df


def build_departements(geojson_df: DataFrame) -> DataFrame:
    """Extrait les attributs départements depuis le GeoJSON Etalab."""
    return geojson_df.select(
        F.col("code").alias("code_departement"),
        F.col("nom"),
        F.col("region").alias("code_region"),
    )


def build_regions(geojson_df: DataFrame) -> DataFrame:
    """Extrait les attributs régions depuis le GeoJSON Etalab."""
    return geojson_df.select(
        F.col("code").alias("code_region"),
        F.col("nom"),
    )


# ── Écriture ──────────────────────────────────────────────────────────────────


def write_parquet(df: DataFrame, out_dir: Path, name: str) -> None:
    """Écrit un DataFrame en Parquet (mode overwrite)."""
    dest = str(out_dir / name)
    logger.info(f"Écriture Parquet : {dest}")
    df.coalesce(1).write.mode("overwrite").parquet(dest)
    logger.info(f"  → OK  ({df.count()} lignes)")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Traitement PySpark des données géographiques.")
    parser.add_argument("--raw-dir", default="data/raw/geo", help="Dossier des fichiers bruts.")
    parser.add_argument("--out-dir", default="data/processed/geo", help="Dossier de sortie Parquet.")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spark = build_spark_session()
    logger.info(f"Spark version : {spark.version}")

    # ── 1. Lecture ────────────────────────────────────────────────────────────
    communes_raw = read_communes_csv(spark, raw_dir)
    population_raw = read_population_xlsx(spark, raw_dir)
    depts_raw = read_geojson_properties(spark, raw_dir / "departements-5m.geojson")
    regions_raw = read_geojson_properties(spark, raw_dir / "regions-5m.geojson")

    # ── 2. Transformations ────────────────────────────────────────────────────
    logger.info("=== Transformation communes ===")
    communes_df = build_communes(communes_raw, population_raw)
    communes_df.printSchema()
    communes_df.show(5, truncate=False)

    logger.info("=== Transformation départements ===")
    depts_df = build_departements(depts_raw)
    depts_df.show(5)

    logger.info("=== Transformation régions ===")
    regions_df = build_regions(regions_raw)
    regions_df.show(5)

    # ── 3. Écriture Parquet ───────────────────────────────────────────────────
    write_parquet(communes_df, out_dir, "communes")
    write_parquet(depts_df, out_dir, "departements")
    write_parquet(regions_df, out_dir, "regions")

    logger.info("=== Traitement terminé ===")
    logger.info(f"Parquet disponibles dans : {out_dir.resolve()}")

    spark.stop()


if __name__ == "__main__":
    main()
