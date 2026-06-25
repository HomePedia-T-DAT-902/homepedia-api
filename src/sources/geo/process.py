"""Job Spark GEO : communes, départements, régions → Parquet."""

import json
import logging

import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, IntegerType, StringType

from src.processing.spark_utils import build_local_friendly_spark_session
from src.sources.geo.config import COMMUNES_CSV_FILE, POPULATION_FILE, POPULATION_SCHEMA, PROCESSED_DIR, RAW_DIR

logger = logging.getLogger(__name__)


def run(raw_dir=RAW_DIR, processed_dir=PROCESSED_DIR) -> None:
    spark = build_local_friendly_spark_session("geo", driver_memory="2g", shuffle_partitions="50")
    try:
        processed_dir.mkdir(parents=True, exist_ok=True)

        communes_raw = _read_communes_csv(spark, raw_dir)
        population_raw = _read_population_xlsx(spark, raw_dir)
        depts_raw = _read_geojson_properties(spark, raw_dir / "departements-5m.geojson")
        regions_raw = _read_geojson_properties(spark, raw_dir / "regions-5m.geojson")

        _write(spark, _build_communes(communes_raw, population_raw), processed_dir / "communes")
        _write(spark, _build_departements(depts_raw), processed_dir / "departements")
        _write(spark, _build_regions(regions_raw), processed_dir / "regions")
    finally:
        spark.stop()


def _read_communes_csv(spark: SparkSession, raw_dir) -> DataFrame:
    df = spark.read.option("header", "true").option("encoding", "UTF-8").csv(str(raw_dir / COMMUNES_CSV_FILE))
    return df.select(
        F.col("code_insee").cast(StringType()).alias("code_commune"),
        F.col("nom_standard").alias("nom"),
        F.col("dep_code").alias("code_departement"),
        F.col("reg_code").alias("code_region"),
        F.col("code_postal"),
        F.col("superficie_km2").cast(DoubleType()).alias("superficie"),
        F.col("latitude_centre").cast(DoubleType()).alias("latitude"),
        F.col("longitude_centre").cast(DoubleType()).alias("longitude"),
    )


def _read_population_xlsx(spark: SparkSession, raw_dir) -> DataFrame:
    pdf = pd.read_excel(raw_dir / POPULATION_FILE, dtype={"codgeo": str})
    pdf = pdf[["codgeo", "p23_pop"]].dropna(subset=["codgeo"])
    pdf["codgeo"] = pdf["codgeo"].str.zfill(5)
    pdf["p23_pop"] = pd.to_numeric(pdf["p23_pop"], errors="coerce")
    return spark.createDataFrame(pdf, schema=POPULATION_SCHEMA)


def _read_geojson_properties(spark: SparkSession, path) -> DataFrame:
    with open(path, encoding="utf-8") as f:
        props = [feat["properties"] for feat in json.load(f)["features"]]
    return spark.createDataFrame(pd.DataFrame(props))


def _build_communes(communes: DataFrame, population: DataFrame) -> DataFrame:
    df = communes.join(population.withColumnRenamed("codgeo", "code_commune"), on="code_commune", how="left")
    df = df.withColumn("population", F.col("p23_pop").cast(IntegerType()))
    df = df.withColumn(
        "densite", F.when(F.col("superficie") > 0, F.round(F.col("population") / F.col("superficie"), 2))
    )
    return df.drop("p23_pop")


def _build_departements(df: DataFrame) -> DataFrame:
    return df.select(F.col("code").alias("code_departement"), F.col("nom"), F.col("region").alias("code_region"))


def _build_regions(df: DataFrame) -> DataFrame:
    return df.select(F.col("code").alias("code_region"), F.col("nom"))


def _write(spark: SparkSession, df: DataFrame, out_path) -> None:
    logger.info(f"[GEO] Écriture → {out_path}  ({df.count()} lignes)")
    df.coalesce(1).write.mode("overwrite").parquet(str(out_path))
