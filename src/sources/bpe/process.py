"""Job Spark BPE : agrégation des équipements par commune → Parquet."""

import logging
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from src.processing.spark_utils import build_local_friendly_spark_session
from src.sources.bpe.config import CATEGORIES, CSV_FILE, OUTPUT_COLUMNS, PROCESSED_DIR, RAW_DIR, TYPEQU_CLES

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR, processed_dir: Path = PROCESSED_DIR) -> None:
    spark = build_local_friendly_spark_session("bpe", driver_memory="2g", shuffle_partitions="100")
    try:
        df = _read(spark, raw_dir)
        df = _normalize(df)
        result = _aggregate(df)
        _write(result, processed_dir)
    finally:
        spark.stop()


def _read(spark: SparkSession, raw_dir: Path) -> DataFrame:
    path = raw_dir / CSV_FILE
    df = spark.read.option("header", "true").option("sep", ";").option("inferSchema", "false").csv(str(path))
    for col in df.columns:
        df = df.withColumnRenamed(col, col.lower())

    depcom = _find_col(df.columns, ["depcom", "code_commune"])
    typequ = _find_col(df.columns, ["typequ", "type_equip"])
    df = df.select(F.col(depcom).alias("code_commune"), F.col(typequ).alias("typequ"))
    logger.info(f"[BPE] {df.count():,} équipements lus")
    return df


def _normalize(df: DataFrame) -> DataFrame:
    df = df.filter(F.col("code_commune").isNotNull() & (F.length(F.trim("code_commune")) > 0))
    df = df.withColumn("code_commune", F.lpad(F.trim("code_commune"), 5, "0"))
    df = df.filter(F.col("typequ").isNotNull() & F.col("typequ").rlike("^[A-F][0-9]{2,3}$"))
    logger.info(f"[BPE] {df.count():,} équipements valides après nettoyage")
    return df


def _aggregate(df: DataFrame) -> DataFrame:
    df = df.withColumn("categorie", F.substring("typequ", 1, 1))
    agg = [F.count("*").alias("nb_equipements_total")]
    agg += [F.sum(F.when(F.col("categorie") == c, 1).otherwise(0)).alias(f"nb_{c.lower()}") for c in CATEGORIES]
    agg += [
        F.sum(F.when(F.col("typequ").isin(codes), 1).otherwise(0)).alias(name) for name, codes in TYPEQU_CLES.items()
    ]
    result = df.groupBy("code_commune").agg(*agg)
    logger.info(f"[BPE] {result.count():,} communes agrégées")
    return result


def _write(df: DataFrame, processed_dir: Path) -> None:
    out = str(processed_dir / "commune_stats")
    processed_dir.mkdir(parents=True, exist_ok=True)
    df.select(*OUTPUT_COLUMNS).write.mode("overwrite").parquet(out)
    logger.info(f"[BPE] Parquet écrit → {out}")


def _find_col(columns: list[str], candidates: list[str]) -> str:
    for c in candidates:
        if c in columns:
            return c
    raise ValueError(f"Aucune colonne trouvée parmi {candidates}. Disponibles : {columns}")
