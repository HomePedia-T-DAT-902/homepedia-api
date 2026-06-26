"""Traitement Spark : agrégation des résultats bac par commune et année."""

import logging
from pathlib import Path

from pyspark.sql import functions as F

from src.processing.spark_utils import build_local_friendly_spark_session
from src.sources.education.config import (
    IVAL_CODE_COL,
    IVAL_FILE,
    IVAL_PRESENTS_COL,
    IVAL_TAUX_COL,
    IVAL_YEAR_COL,
    PROCESSED_DIR,
    RAW_DIR,
)

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR, processed_dir: Path = PROCESSED_DIR) -> None:
    spark = build_local_friendly_spark_session("education", driver_memory="2g")
    try:
        _process(spark, raw_dir, processed_dir)
    finally:
        spark.stop()


def _process(spark, raw_dir: Path, processed_dir: Path) -> None:
    logger.info("[Education] Lecture du fichier IVAL...")
    df = (
        spark.read.option("header", "true").option("sep", ";").option("encoding", "UTF-8").csv(str(raw_dir / IVAL_FILE))
    )
    logger.info(f"[Education] {df.count():,} lignes brutes")

    # Garder uniquement les communes (code 5 chars)
    df = df.filter(F.length(F.col(IVAL_CODE_COL)) == 5)

    # Convertir les types
    df = df.withColumn(IVAL_YEAR_COL, F.col(IVAL_YEAR_COL).cast("integer"))
    df = df.withColumn(IVAL_PRESENTS_COL, F.col(IVAL_PRESENTS_COL).cast("integer"))
    df = df.withColumn(IVAL_TAUX_COL, F.regexp_replace(F.col(IVAL_TAUX_COL), ",", ".").cast("double"))

    # Agrégation par (commune, année) : somme présentés, moyenne pondérée taux
    df_agg = df.groupBy(IVAL_CODE_COL, IVAL_YEAR_COL).agg(
        F.sum(IVAL_PRESENTS_COL).cast("integer").alias("bac_presents"),
        F.round(
            F.sum(F.col(IVAL_PRESENTS_COL) * F.col(IVAL_TAUX_COL)) / F.sum(IVAL_PRESENTS_COL),
            1,
        ).alias("bac_taux_reussite"),
    )

    # Renommage final
    df_out = (
        df_agg.withColumnRenamed(IVAL_CODE_COL, "code_commune")
        .withColumnRenamed(IVAL_YEAR_COL, "annee")
        .filter(F.col("code_commune").isNotNull() & F.col("annee").isNotNull())
        .orderBy("code_commune", "annee")
    )

    n = df_out.count()
    logger.info(f"[Education] {n:,} lignes (commune × année) à écrire")

    out = processed_dir / "bac"
    df_out.write.mode("overwrite").parquet(str(out))
    logger.info(f"[Education] Parquet écrit : {out}")
