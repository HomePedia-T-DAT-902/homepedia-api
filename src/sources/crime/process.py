"""Traitement Spark : pivot long → large, agrégation par commune et année."""

import logging
from pathlib import Path

from pyspark.sql import functions as F

from src.processing.spark_utils import build_local_friendly_spark_session
from src.sources.crime.config import (
    CATEGORIES,
    CODGEO_COL,
    PROCESSED_DIR,
    RAW_DIR,
    RAW_FILE,
)

logger = logging.getLogger(__name__)


def run(raw_dir: Path = RAW_DIR, processed_dir: Path = PROCESSED_DIR) -> None:
    spark = build_local_friendly_spark_session("crime", driver_memory="4g")
    try:
        _process(spark, raw_dir, processed_dir)
    finally:
        spark.stop()


def _process(spark, raw_dir: Path, processed_dir: Path) -> None:
    logger.info("[Crime] Lecture du fichier Parquet...")
    df = spark.read.parquet(str(raw_dir / RAW_FILE))
    logger.info(f"[Crime] {df.count():,} lignes brutes")

    # Communes uniquement (code 5 chars) + diffusées uniquement
    df = df.filter((F.length(F.col(CODGEO_COL)) == 5) & (F.col("est_diffuse") == "diff"))

    # Colonne catégorie
    cat_expr = None
    for cat, indicateurs in CATEGORIES.items():
        cond = F.col("indicateur").isin(indicateurs)
        cat_expr = F.when(cond, cat) if cat_expr is None else cat_expr.when(cond, cat)
    df = df.withColumn("categorie", cat_expr.otherwise(None)).filter(F.col("categorie").isNotNull())

    # Agrégation par (commune, année, catégorie) — somme nombre ET taux
    df_agg = df.groupBy(CODGEO_COL, "annee", "categorie").agg(
        F.sum("nombre").cast("integer").alias("nb"),
        F.round(F.sum("taux_pour_mille"), 1).alias("taux"),
    )

    # Pivot avec deux métriques
    cat_cols = list(CATEGORIES.keys())
    df_wide = (
        df_agg.groupBy(CODGEO_COL, "annee")
        .pivot("categorie", cat_cols)
        .agg(F.first("nb").alias("nb"), F.first("taux").alias("taux"))
    )

    # Renommage : cambriolages_nb → cambriolages_nombre, cambriolages_taux → cambriolages_pour_mille
    df_wide = df_wide.withColumnRenamed(CODGEO_COL, "code_commune")
    for cat in cat_cols:
        df_wide = df_wide.withColumnRenamed(f"{cat}_nb", f"{cat}_nombre")
        df_wide = df_wide.withColumnRenamed(f"{cat}_taux", f"{cat}_pour_mille")

    df_wide = df_wide.orderBy("code_commune", "annee")
    n = df_wide.count()
    logger.info(f"[Crime] {n:,} lignes (commune × année) à écrire")

    out = processed_dir / "securite"
    df_wide.write.mode("overwrite").parquet(str(out))
    logger.info(f"[Crime] Parquet écrit : {out}")
