"""Traitement PySpark des données DVF."""

import logging
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

from src.processing.spark_utils import build_local_friendly_spark_session
from src.sources.dvf.config import (
    OUTPUT_COLS,
    PRIX_M2_MAX,
    PRIX_M2_MIN,
    PRIX_MIN,
    PROCESSED_DIR,
    RAW_DIR,
    SURFACE_MAX,
    SURFACE_MIN,
)

logger = logging.getLogger(__name__)

GEO_DVF_SCHEMA = StructType(
    [
        StructField("id_mutation", StringType(), True),
        StructField("date_mutation", StringType(), True),
        StructField("numero_disposition", StringType(), True),
        StructField("nature_mutation", StringType(), True),
        StructField("valeur_fonciere", DoubleType(), True),
        StructField("adresse_numero", StringType(), True),
        StructField("adresse_suffixe", StringType(), True),
        StructField("adresse_nom_voie", StringType(), True),
        StructField("adresse_code_voie", StringType(), True),
        StructField("code_postal", StringType(), True),
        StructField("code_commune", StringType(), True),
        StructField("nom_commune", StringType(), True),
        StructField("code_departement", StringType(), True),
        StructField("ancien_code_commune", StringType(), True),
        StructField("ancien_nom_commune", StringType(), True),
        StructField("id_parcelle", StringType(), True),
        StructField("ancien_id_parcelle", StringType(), True),
        StructField("numero_volume", StringType(), True),
        StructField("lot1_numero", StringType(), True),
        StructField("lot1_surface_carrez", DoubleType(), True),
        StructField("lot2_numero", StringType(), True),
        StructField("lot2_surface_carrez", DoubleType(), True),
        StructField("lot3_numero", StringType(), True),
        StructField("lot3_surface_carrez", DoubleType(), True),
        StructField("lot4_numero", StringType(), True),
        StructField("lot4_surface_carrez", DoubleType(), True),
        StructField("lot5_numero", StringType(), True),
        StructField("lot5_surface_carrez", DoubleType(), True),
        StructField("nombre_lots", IntegerType(), True),
        StructField("code_type_local", StringType(), True),
        StructField("type_local", StringType(), True),
        StructField("surface_reelle_bati", DoubleType(), True),
        StructField("nombre_pieces_principales", IntegerType(), True),
        StructField("code_nature_culture", StringType(), True),
        StructField("nature_culture", StringType(), True),
        StructField("code_nature_culture_speciale", StringType(), True),
        StructField("nature_culture_speciale", StringType(), True),
        StructField("surface_terrain", DoubleType(), True),
        StructField("longitude", DoubleType(), True),
        StructField("latitude", DoubleType(), True),
    ]
)

_DGFIP_COL_MAP = {
    "No disposition": "numero_disposition",
    "Date mutation": "date_mutation_raw",
    "Nature mutation": "nature_mutation",
    "Valeur fonciere": "valeur_fonciere_raw",
    "Code voie": "adresse_code_voie",
    "Voie": "adresse_nom_voie",
    "Code postal": "code_postal",
    "Commune": "nom_commune",
    "Code departement": "code_departement",
    "Code commune": "code_commune_court",
    "Nombre de lots": "nombre_lots",
    "Code type local": "code_type_local",
    "Type local": "type_local",
    "Surface reelle bati": "surface_reelle_bati",
    "Nombre pieces principales": "nombre_pieces_principales",
    "Nature culture": "nature_culture",
    "Nature culture speciale": "nature_culture_speciale",
    "Surface terrain": "surface_terrain",
}

_COMMON_COLS = [
    "id_mutation",
    "date_mutation",
    "nature_mutation",
    "valeur_fonciere",
    "code_commune",
    "type_local",
    "surface_reelle_bati",
    "nombre_pieces_principales",
    "surface_terrain",
    "longitude",
    "latitude",
    "source",
]


def run(raw_dir: Path = RAW_DIR, processed_dir: Path = PROCESSED_DIR) -> None:
    spark = build_local_friendly_spark_session("spark_dvf", driver_memory="4g", shuffle_partitions="200")
    logger.info(f"SparkSession — master : {spark.conf.get('spark.master')}")

    dfs = []
    try:
        dfs.append(_read_geo(spark, raw_dir))
    except FileNotFoundError as e:
        logger.warning(f"Geo-DVF ignoré : {e}")
    try:
        dfs.append(_read_dgfip(spark, raw_dir))
    except FileNotFoundError as e:
        logger.warning(f"DVF DGFiP ignoré : {e}")

    if not dfs:
        raise FileNotFoundError(f"Aucun fichier DVF dans {raw_dir}")

    if len(dfs) == 1:
        df = dfs[0].select(*_COMMON_COLS)
    else:
        df = dfs[0].select(*_COMMON_COLS).unionByName(dfs[1].select(*_COMMON_COLS))

    logger.info(f"[Union] Total : {df.count():,} lignes")

    df = _filter_and_normalize(df)
    df = _deduplicate(df)
    df = _compute_prix_m2(df)
    df = _filter_anomalies(df)
    df = df.withColumn("annee", F.year("date_mutation").cast(IntegerType()))
    df = df.select(*OUTPUT_COLS)

    processed_dir.mkdir(parents=True, exist_ok=True)
    df.write.mode("overwrite").partitionBy("annee").parquet(str(processed_dir))
    total = df.count()
    logger.info(f"[DVF] Export Parquet → {processed_dir}  ({total:,} transactions)")

    spark.stop()


def _read_geo(spark: SparkSession, raw_dir: Path) -> DataFrame:
    geo_dir = raw_dir / "geo"
    csv_files = sorted(geo_dir.glob("dvf_*.csv")) if geo_dir.exists() else []
    if not csv_files:
        raise FileNotFoundError(f"Aucun Geo-DVF dans {raw_dir / 'geo'}")
    logger.info(f"[Geo-DVF] {len(csv_files)} fichier(s)")
    df = (
        spark.read.option("header", "true")
        .option("encoding", "UTF-8")
        .option("sep", ",")
        .schema(GEO_DVF_SCHEMA)
        .csv([str(f) for f in csv_files])
    )
    df = df.withColumn("date_mutation", F.to_date("date_mutation", "yyyy-MM-dd"))
    return df.withColumn("source", F.lit("geo"))


def _read_dgfip(spark: SparkSession, raw_dir: Path) -> DataFrame:
    dgfip_dir = raw_dir / "dgfip"
    csv_files = sorted(dgfip_dir.glob("dvf_*.csv")) if dgfip_dir.exists() else []
    if not csv_files:
        raise FileNotFoundError(f"Aucun DVF DGFiP dans {raw_dir / 'dgfip'}")
    logger.info(f"[DGFiP] {len(csv_files)} fichier(s)")
    df = (
        spark.read.option("header", "true")
        .option("encoding", "ISO-8859-1")
        .option("sep", "|")
        .option("inferSchema", "false")
        .csv([str(f) for f in csv_files])
    )
    for raw_name, clean_name in _DGFIP_COL_MAP.items():
        if raw_name in df.columns:
            df = df.withColumnRenamed(raw_name, clean_name)
    df = df.withColumn(
        "valeur_fonciere",
        F.regexp_replace("valeur_fonciere_raw", ",", ".").cast(DoubleType()),
    ).drop("valeur_fonciere_raw")
    df = df.withColumn("date_mutation", F.to_date("date_mutation_raw", "dd/MM/yyyy")).drop("date_mutation_raw")
    df = df.withColumn(
        "code_commune",
        F.concat(F.col("code_departement"), F.lpad(F.col("code_commune_court"), 3, "0")),
    ).drop("code_commune_court")
    df = df.withColumn("surface_reelle_bati", F.col("surface_reelle_bati").cast(DoubleType()))
    df = df.withColumn("surface_terrain", F.col("surface_terrain").cast(DoubleType()))
    df = df.withColumn("nombre_pieces_principales", F.col("nombre_pieces_principales").cast(IntegerType()))
    df = df.withColumn("id_mutation", F.lit(None).cast(StringType()))
    df = df.withColumn("longitude", F.lit(None).cast(DoubleType()))
    df = df.withColumn("latitude", F.lit(None).cast(DoubleType()))
    return df.withColumn("source", F.lit("dgfip"))


def _filter_and_normalize(df: DataFrame) -> DataFrame:
    df = df.filter(F.col("nature_mutation") == "Vente")
    df = df.filter(F.col("type_local").isin("Maison", "Appartement"))
    return df.withColumn("code_commune", F.lpad(F.col("code_commune"), 5, "0"))


def _deduplicate(df: DataFrame) -> DataFrame:
    """Déduplique les mutations multi-lots : somme les surfaces, garde le premier lot pour le reste."""
    geo = df.filter(F.col("source") == "geo")
    dgfip = df.filter(F.col("source") == "dgfip")

    geo_agg = geo.groupBy("id_mutation").agg(
        F.first("date_mutation").alias("date_mutation"),
        F.first("nature_mutation").alias("nature_mutation"),
        F.first("valeur_fonciere").alias("valeur_fonciere"),
        F.first("code_commune").alias("code_commune"),
        F.first("type_local").alias("type_local"),
        F.sum("surface_reelle_bati").alias("surface_reelle_bati"),
        F.first("nombre_pieces_principales").alias("nombre_pieces_principales"),
        F.sum("surface_terrain").alias("surface_terrain"),
        F.first("longitude").alias("longitude"),
        F.first("latitude").alias("latitude"),
        F.first("source").alias("source"),
    )

    dgfip_key = ["date_mutation", "valeur_fonciere", "code_commune", "nature_mutation", "type_local"]
    dgfip_agg = dgfip.groupBy(*dgfip_key).agg(
        F.sum("surface_reelle_bati").alias("surface_reelle_bati"),
        F.first("nombre_pieces_principales").alias("nombre_pieces_principales"),
        F.sum("surface_terrain").alias("surface_terrain"),
        F.lit(None).cast(StringType()).alias("id_mutation"),
        F.lit(None).cast(DoubleType()).alias("longitude"),
        F.lit(None).cast(DoubleType()).alias("latitude"),
        F.first("source").alias("source"),
    )

    result = geo_agg.unionByName(dgfip_agg)
    logger.info(f"[Déduplication] {result.count():,} mutations uniques")
    return result


def _compute_prix_m2(df: DataFrame) -> DataFrame:
    return df.withColumn(
        "prix_m2",
        F.when(
            F.col("surface_reelle_bati") > 0,
            F.round(F.col("valeur_fonciere") / F.col("surface_reelle_bati"), 2),
        ).otherwise(F.lit(None).cast(DoubleType())),
    )


def _filter_anomalies(df: DataFrame) -> DataFrame:
    before = df.count()
    df = df.filter(
        (F.col("valeur_fonciere") >= PRIX_MIN)
        & (F.col("surface_reelle_bati") >= SURFACE_MIN)
        & (F.col("surface_reelle_bati") <= SURFACE_MAX)
        & (F.col("prix_m2") >= PRIX_M2_MIN)
        & (F.col("prix_m2") <= PRIX_M2_MAX)
    )
    removed = before - df.count()
    logger.info(f"[Anomalies] {removed:,} lignes supprimées ({removed / before * 100:.1f}%)")
    return df
