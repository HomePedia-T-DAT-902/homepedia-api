"""Utilitaires partagés pour les jobs Spark."""

from __future__ import annotations

import os

from pyspark.sql import SparkSession


def build_local_friendly_spark_session(app_name: str, driver_memory: str, shuffle_partitions: str) -> SparkSession:
    """
    Crée une SparkSession robuste en local, notamment sous Windows.

    Sous Windows, Hadoop peut tenter d'utiliser des bindings natifs absents
    (`NativeIO$Windows.access0`) lors du commit des fichiers Parquet.
    On force ici un backend de fichiers local plus simple pour éviter ce plantage.
    """
    master = os.environ.get("SPARK_MASTER_URL", "local[*]")

    builder = (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.driver.memory", driver_memory)
        .config("spark.sql.shuffle.partitions", shuffle_partitions)
        .config("spark.driver.extraJavaOptions", "-Djava.security.manager=allow")
        .config("spark.executor.extraJavaOptions", "-Djava.security.manager=allow")
        .config("spark.hadoop.io.native.lib.available", "false")
        .config("spark.hadoop.fs.file.impl", "org.apache.hadoop.fs.RawLocalFileSystem")
        .config("spark.hadoop.fs.local.impl", "org.apache.hadoop.fs.RawLocalFileSystem")
        .config("spark.hadoop.fs.file.impl.disable.cache", "true")
    )

    return builder.getOrCreate()
