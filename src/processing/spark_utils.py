"""
Utilitaire partagé pour créer une SparkSession dans les jobs de traitement.

Lit SPARK_MASTER_URL depuis l'environnement :
  - défini (ex: spark://spark-master:7077) → mode cluster Docker
  - absent ou vide                         → local[*] (tous les cores, dev/CI)
"""

import logging
import os

from pyspark.sql import SparkSession

logger = logging.getLogger(__name__)


def build_local_friendly_spark_session(
    app_name: str,
    driver_memory: str = "2g",
    shuffle_partitions: str = "100",
) -> SparkSession:
    master = os.environ.get("SPARK_MASTER_URL", "local[*]")
    logger.info(f"SparkSession '{app_name}' — master={master}, driver_memory={driver_memory}")

    return (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.driver.memory", driver_memory)
        .config("spark.sql.shuffle.partitions", shuffle_partitions)
        .config("spark.sql.legacy.timeParserPolicy", "LEGACY")
        .getOrCreate()
    )
