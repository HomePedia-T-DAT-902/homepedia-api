"""Traitement PySpark des données DPE."""

import logging
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType

from src.processing.spark_utils import build_local_friendly_spark_session
from src.sources.dpe.config import (
    CLASSES_VALIDES,
    COMMUNE_STATS_OUTPUT_COLS,
    CONSO_MAX,
    CONSO_MIN,
    DIAG_OUTPUT_COLS,
    PROCESSED_DIR,
    RAW_DIR,
)

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR, processed_dir: Path = PROCESSED_DIR) -> None:
    spark = build_local_friendly_spark_session("spark_dpe", driver_memory="4g", shuffle_partitions="200")
    logger.info(f"SparkSession — master : {spark.conf.get('spark.master')}")

    dfs = []
    try:
        dfs.append(_read_nouveau(spark, raw_dir))
    except FileNotFoundError as e:
        logger.warning(f"DPE nouveau ignoré : {e}")
    try:
        dfs.append(_read_ancien(spark, raw_dir))
    except FileNotFoundError as e:
        logger.warning(f"DPE ancien ignoré : {e}")

    if not dfs:
        raise FileNotFoundError(f"Aucun fichier DPE dans {raw_dir}")

    df = dfs[0] if len(dfs) == 1 else dfs[0].unionByName(dfs[1])
    logger.info(f"[Union] Total : {df.count():,} lignes")

    df = _normalize(df)
    df.cache()
    total = df.count()
    logger.info(f"[Cache] {total:,} DPE valides")

    processed_dir.mkdir(parents=True, exist_ok=True)

    diag_path = str(processed_dir / "diagnostics")
    df.select(*DIAG_OUTPUT_COLS).write.mode("overwrite").parquet(diag_path)
    logger.info(f"[DPE] Export diagnostics → {diag_path}")

    commune_df = _aggregate_by_commune(df)
    commune_path = str(processed_dir / "commune_stats")
    commune_df.select(*COMMUNE_STATS_OUTPUT_COLS).write.mode("overwrite").parquet(commune_path)
    logger.info(f"[DPE] Export commune_stats → {commune_path}  ({commune_df.count():,} communes)")

    df.unpersist()
    spark.stop()


def _read_nouveau(spark: SparkSession, raw_dir: Path) -> DataFrame:
    path = raw_dir / "dpe_nouveau.csv"
    if not path.exists():
        raise FileNotFoundError(f"Fichier absent : {path}")
    logger.info(f"[DPE nouveau] Lecture : {path}")
    df = (
        spark.read.option("header", "true")
        .option("encoding", "UTF-8")
        .option("sep", ",")
        .option("inferSchema", "false")
        .csv(str(path))
    )
    conso_col = next(
        (c for c in df.columns if "conso_5" in c.lower() and "par_m2_ef" in c.lower()),
        None,
    )
    if not conso_col:
        raise ValueError(f"Colonne consommation introuvable. Colonnes : {df.columns[:20]}")
    logger.info(f"[DPE nouveau] Colonne consommation : '{conso_col}'")
    return df.select(
        F.col("code_insee_ban").alias("code_commune"),
        F.to_date("date_etablissement_dpe", "yyyy-MM-dd").alias("date_diagnostic"),
        F.col("etiquette_dpe").alias("classe_energie"),
        F.col(conso_col).cast(DoubleType()).alias("consommation_moyenne"),
    ).withColumn("source", F.lit("nouveau"))


def _read_ancien(spark: SparkSession, raw_dir: Path) -> DataFrame:
    path = raw_dir / "dpe_ancien.csv"
    if not path.exists():
        raise FileNotFoundError(f"Fichier absent : {path}")
    logger.info(f"[DPE ancien] Lecture : {path}")
    df = (
        spark.read.option("header", "true")
        .option("encoding", "UTF-8")
        .option("sep", ",")
        .option("inferSchema", "false")
        .csv(str(path))
    )
    before = df.count()
    if "dpe_vierge" in df.columns:
        df = df.filter(F.col("dpe_vierge") == "0")
    if "est_efface" in df.columns:
        df = df.filter(F.col("est_efface") == "0")
    logger.info(f"[DPE ancien] {before:,} → {df.count():,} après filtre vierge/effacé")

    commune_col = (
        "code_insee_commune_actualise" if "code_insee_commune_actualise" in df.columns else "code_insee_commune"
    )
    return df.select(
        F.col(commune_col).alias("code_commune"),
        F.coalesce(
            F.to_date("date_etablissement_dpe", "yyyy-MM-dd"),
            F.to_date("date_etablissement_dpe", "dd/MM/yyyy"),
        ).alias("date_diagnostic"),
        F.col("classe_consommation_energie").alias("classe_energie"),
        F.col("consommation_energie").cast(DoubleType()).alias("consommation_moyenne"),
    ).withColumn("source", F.lit("ancien"))


def _normalize(df: DataFrame) -> DataFrame:
    df = df.withColumn("code_commune", F.lpad(F.trim(F.col("code_commune")), 5, "0"))
    df = df.withColumn("classe_energie", F.upper(F.trim(F.col("classe_energie"))))
    before = df.count()
    df = df.filter(F.col("classe_energie").isin(list(CLASSES_VALIDES)))
    logger.info(f"[Normalisation] {before - df.count():,} lignes hors A-G supprimées")
    df = df.filter(
        F.col("consommation_moyenne").isNotNull()
        & (F.col("consommation_moyenne") > CONSO_MIN)
        & (F.col("consommation_moyenne") <= CONSO_MAX)
    )
    df = df.filter(F.col("code_commune").isNotNull() & (F.length("code_commune") == 5))
    return df


def _aggregate_by_commune(df: DataFrame) -> DataFrame:
    agg_df = df.groupBy("code_commune").agg(
        F.count("*").alias("nb_dpe_total"),
        *[
            F.sum(F.when(F.col("classe_energie") == cls.upper(), 1).otherwise(0)).alias(f"nb_classe_{cls}")
            for cls in ["a", "b", "c", "d", "e", "f", "g"]
        ],
        F.round(F.avg("consommation_moyenne"), 1).alias("consommation_moyenne_commune"),
    )
    for cls in ["a", "b", "c", "d", "e", "f", "g"]:
        agg_df = agg_df.withColumn(
            f"pct_classe_{cls}",
            F.round(F.col(f"nb_classe_{cls}") / F.col("nb_dpe_total") * 100, 1),
        )
    logger.info(f"[Agrégation] {agg_df.count():,} communes avec données DPE")
    return agg_df
