"""
Traitement PySpark des données DPE — Diagnostics de Performance Énergétique (P2-2).

Fusionne et nettoie 2 sources de formats différents :
  - DPE nouveau (post-juillet 2021) : data/raw/dpe/dpe_nouveau.csv
      CSV UTF-8, ~200 colonnes, noms avec espaces, classes A-G dans `etiquette_dpe`
  - DPE ancien  (pré-juillet 2021)  : data/raw/dpe/dpe_ancien.csv
      CSV converti depuis dump MySQL, classes A-G dans `classe_consommation_energie`
      Filtres nécessaires : dpe_vierge=0 et est_efface=0

Étapes :
  1. Lecture des deux CSV avec schémas partiels (colonnes utilisées uniquement)
  2. Normalisation des colonnes vers un schéma commun
  3. Union des deux sources
  4. Validation des classes énergie (A-G uniquement)
  5. Filtrage des consommations aberrantes
  6. Export 1 — diagnostics individuels nettoyés (pour table dpe_diagnostics)
  7. Agrégation par commune → distribution des classes + consommation moyenne
  8. Export 2 — stats DPE par commune (pour spark_aggregations + commune_statistics)

Sorties (data/processed/dpe/) :
  - diagnostics/      → un enregistrement par DPE individuel (~18M lignes)
  - commune_stats/    → un enregistrement par commune (agrégation des classes)

Usage :
    docker-compose run --rm processing python -m src.processing.spark_dpe
    docker-compose run --rm processing python -m src.processing.spark_dpe --raw-dir data/raw/dpe --out-dir data/processed/dpe
"""

import argparse
import logging
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType

from src.processing.spark_utils import build_local_friendly_spark_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/dpe")
OUT_DIR = Path("data/processed/dpe")

# ── Seuils de filtrage ────────────────────────────────────────────────────────
CONSO_MIN = 0  # kWh/m²/an — consommation nulle ou négative = invalide
CONSO_MAX = 3_000  # kWh/m²/an — au-dessus = erreur de saisie (max réel ~900 pour F/G)

CLASSES_VALIDES = {"A", "B", "C", "D", "E", "F", "G"}

# ── Colonnes de sortie communes ───────────────────────────────────────────────
DIAG_OUTPUT_COLS = [
    "code_commune",  # str  5 chars INSEE
    "date_diagnostic",  # date
    "classe_energie",  # str  A-G
    "consommation_moyenne",  # double kWh/m²/an
    "source",  # str  "nouveau" | "ancien"
]

COMMUNE_STATS_OUTPUT_COLS = [
    "code_commune",
    "nb_dpe_total",
    "nb_classe_a",
    "nb_classe_b",
    "nb_classe_c",
    "nb_classe_d",
    "nb_classe_e",
    "nb_classe_f",
    "nb_classe_g",
    "pct_classe_a",
    "pct_classe_b",
    "pct_classe_c",
    "pct_classe_d",
    "pct_classe_e",
    "pct_classe_f",
    "pct_classe_g",
    "consommation_moyenne_commune",
]


# ── SparkSession ──────────────────────────────────────────────────────────────


def build_spark_session(app_name: str = "spark_dpe") -> SparkSession:
    return build_local_friendly_spark_session(app_name, driver_memory="4g", shuffle_partitions="200")


# ── Lecture ───────────────────────────────────────────────────────────────────


def read_dpe_nouveau(spark: SparkSession, raw_dir: Path) -> DataFrame:
    """
    Lit le DPE nouveau (post-juillet 2021).

    Colonnes clés :
      - code_insee_ban          → code_commune
      - date_etablissement_dpe  → date_diagnostic
      - etiquette_dpe           → classe_energie
      - "conso_5 usages_par_m2_ef" → consommation_moyenne  (espace dans le nom !)
    """
    path = raw_dir / "dpe_nouveau.csv"
    if not path.exists():
        raise FileNotFoundError(f"Fichier absent : {path}")

    logger.info(f"[DPE nouveau] Lecture : {path}")

    # Lire tout en string d'abord — le CSV a ~200 colonnes avec des noms bizarres
    df = (
        spark.read.option("header", "true")
        .option("encoding", "UTF-8")
        .option("sep", ",")
        .option("inferSchema", "false")
        .csv(str(path))
    )

    # Sélectionner et renommer les colonnes utiles
    # Note : "conso_5 usages_par_m2_ef" contient un espace — backtick dans Spark SQL
    conso_col = _find_conso_column_nouveau(df)

    df = df.select(
        F.col("code_insee_ban").alias("code_commune"),
        F.col("date_etablissement_dpe").alias("date_diagnostic_raw"),
        F.col("etiquette_dpe").alias("classe_energie"),
        F.col(conso_col).alias("consommation_moyenne"),
    )

    df = df.withColumn("date_diagnostic", F.to_date("date_diagnostic_raw", "yyyy-MM-dd")).drop("date_diagnostic_raw")
    df = df.withColumn("consommation_moyenne", F.col("consommation_moyenne").cast(DoubleType()))
    df = df.withColumn("source", F.lit("nouveau"))

    count = df.count()
    logger.info(f"[DPE nouveau] {count:,} lignes lues")
    return df


def _find_conso_column_nouveau(df: DataFrame) -> str:
    """
    Trouve le nom exact de la colonne de consommation dans le DPE nouveau.
    Le dataset ADEME a parfois un espace dans le nom : "conso_5 usages_par_m2_ef"
    ou "conso_5_usages_par_m2_ef" selon la version exportée.
    """
    for col in df.columns:
        if "conso_5" in col.lower() and "par_m2_ef" in col.lower():
            logger.info(f"[DPE nouveau] Colonne consommation trouvée : '{col}'")
            return col

    raise ValueError(f"Colonne de consommation introuvable. Colonnes disponibles : {df.columns[:20]}")


def read_dpe_ancien(spark: SparkSession, raw_dir: Path) -> DataFrame:
    """
    Lit le DPE ancien (pré-juillet 2021), converti depuis dump MySQL.

    Colonnes clés :
      - code_insee_commune         → code_commune
      - date_etablissement_dpe     → date_diagnostic
      - classe_consommation_energie → classe_energie
      - consommation_energie        → consommation_moyenne
    Filtres obligatoires :
      - dpe_vierge = '0'   (DPE sans consommation réelle à exclure)
      - est_efface = '0'   (DPE annulés à exclure)
    """
    path = raw_dir / "dpe_ancien.csv"
    if not path.exists():
        raise FileNotFoundError(f"Fichier absent : {path}")

    logger.info(f"[DPE ancien] Lecture : {path}")

    df = (
        spark.read.option("header", "true")
        .option("encoding", "UTF-8")  # converti en UTF-8 par download_dpe.py
        .option("sep", ",")
        .option("inferSchema", "false")
        .csv(str(path))
    )

    # Filtrer les DPE vierges et annulés avant tout traitement
    if "dpe_vierge" in df.columns:
        df = df.filter(F.col("dpe_vierge") == "0")
    if "est_efface" in df.columns:
        df = df.filter(F.col("est_efface") == "0")

    # Gérer les deux noms possibles pour code_commune
    # (la table principale du dump s'appelle td001_dpe)
    commune_col = (
        "code_insee_commune_actualise" if "code_insee_commune_actualise" in df.columns else "code_insee_commune"
    )

    df = df.select(
        F.col(commune_col).alias("code_commune"),
        F.col("date_etablissement_dpe").alias("date_diagnostic_raw"),
        F.col("classe_consommation_energie").alias("classe_energie"),
        F.col("consommation_energie").alias("consommation_moyenne"),
    )

    df = df.withColumn(
        "date_diagnostic",
        F.coalesce(
            F.to_date("date_diagnostic_raw", "yyyy-MM-dd"),
            F.to_date("date_diagnostic_raw", "dd/MM/yyyy"),
        ),
    ).drop("date_diagnostic_raw")
    df = df.withColumn("consommation_moyenne", F.col("consommation_moyenne").cast(DoubleType()))
    df = df.withColumn("source", F.lit("ancien"))

    count = df.count()
    logger.info(f"[DPE ancien] {count:,} lignes retenues")
    return df


# ── Transformations ───────────────────────────────────────────────────────────


def normalize_classe_energie(df: DataFrame) -> DataFrame:
    """
    Normalise la classe énergie :
    - Majuscule (certaines valeurs sont en minuscule dans l'ancien DPE)
    - Trim des espaces
    - Conserve uniquement A-G
    """
    df = df.withColumn(
        "classe_energie",
        F.upper(F.trim(F.col("classe_energie"))),
    )
    df = df.filter(F.col("classe_energie").isin(list(CLASSES_VALIDES)))
    return df


def normalize_code_commune(df: DataFrame) -> DataFrame:
    """S'assure que code_commune fait 5 chars (padding gauche avec 0)."""
    return df.withColumn(
        "code_commune",
        F.lpad(F.trim(F.col("code_commune")), 5, "0"),
    )


def filter_consommation(df: DataFrame) -> DataFrame:
    """Filtre les consommations aberrantes ou nulles."""
    df = df.filter(
        F.col("consommation_moyenne").isNotNull()
        & (F.col("consommation_moyenne") > CONSO_MIN)
        & (F.col("consommation_moyenne") <= CONSO_MAX)
    )
    return df


# ── Agrégation par commune ────────────────────────────────────────────────────


def aggregate_by_commune(df: DataFrame) -> DataFrame:
    """
    Agrège les DPE par commune :
    - Nombre total de DPE
    - Nombre et % par classe (A-G)
    - Consommation moyenne de la commune

    Résultat : une ligne par commune.
    """
    logger.info("[Agrégation] Calcul des stats DPE par commune...")

    agg_df = df.groupBy("code_commune").agg(
        F.count("*").alias("nb_dpe_total"),
        # Comptes par classe
        F.sum(F.when(F.col("classe_energie") == "A", 1).otherwise(0)).alias("nb_classe_a"),
        F.sum(F.when(F.col("classe_energie") == "B", 1).otherwise(0)).alias("nb_classe_b"),
        F.sum(F.when(F.col("classe_energie") == "C", 1).otherwise(0)).alias("nb_classe_c"),
        F.sum(F.when(F.col("classe_energie") == "D", 1).otherwise(0)).alias("nb_classe_d"),
        F.sum(F.when(F.col("classe_energie") == "E", 1).otherwise(0)).alias("nb_classe_e"),
        F.sum(F.when(F.col("classe_energie") == "F", 1).otherwise(0)).alias("nb_classe_f"),
        F.sum(F.when(F.col("classe_energie") == "G", 1).otherwise(0)).alias("nb_classe_g"),
        # Consommation moyenne de la commune
        F.round(F.avg("consommation_moyenne"), 1).alias("consommation_moyenne_commune"),
    )

    # Calcul des pourcentages
    for classe in ["a", "b", "c", "d", "e", "f", "g"]:
        agg_df = agg_df.withColumn(
            f"pct_classe_{classe}",
            F.round(F.col(f"nb_classe_{classe}") / F.col("nb_dpe_total") * 100, 1),
        )

    count = agg_df.count()
    logger.info(f"[Agrégation] {count:,} communes avec données DPE")
    return agg_df


# ── Pipeline principal ────────────────────────────────────────────────────────


def run(raw_dir: Path, out_dir: Path) -> None:
    spark = build_spark_session()
    logger.info(f"SparkSession démarrée — master : {spark.conf.get('spark.master')}")

    # 1. Lecture
    nouveau_df = read_dpe_nouveau(spark, raw_dir)
    ancien_df = read_dpe_ancien(spark, raw_dir)

    # 2. Union sur colonnes communes
    # ATTENTION : consommation_moyenne mélange des unités hétérogènes :
    #   - DPE nouveau : kWhEF/m²/an  (énergie finale, colonne conso_5_usages_par_m2_ef)
    #   - DPE ancien  : kWhEP/m²/an  (énergie primaire, colonne consommation_energie)
    # Les classes A-G restent comparables. La consommation_moyenne_commune est indicative.
    logger.warning(
        "[DPE] consommation_moyenne mélange EF (nouveau) et CEP (ancien) — "
        "les classes A-G sont fiables, la consommation_moyenne_commune est indicative uniquement"
    )
    df = nouveau_df.unionByName(ancien_df)
    logger.info("[Union] DPE nouveau + ancien fusionnés")

    # 3. Normalisation
    df = normalize_code_commune(df)
    df = normalize_classe_energie(df)
    df = filter_consommation(df)

    # Supprimer les lignes sans code_commune valide
    df = df.filter(F.col("code_commune").isNotNull() & (F.length("code_commune") == 5))

    # Mettre en cache pour éviter de recalculer deux fois (diagnostics + agrégation)
    df.cache()
    total = df.count()
    logger.info(f"[Cache] {total:,} DPE valides en mémoire")

    # 4. Export 1 — diagnostics individuels
    diag_path = str(out_dir / "diagnostics")
    logger.info(f"Export diagnostics → {diag_path}")
    (df.select(*DIAG_OUTPUT_COLS).write.mode("overwrite").parquet(diag_path))

    # 5. Agrégation par commune + Export 2
    commune_df = aggregate_by_commune(df)
    commune_path = str(out_dir / "commune_stats")
    logger.info(f"Export commune_stats → {commune_path}")
    (commune_df.select(*COMMUNE_STATS_OUTPUT_COLS).write.mode("overwrite").parquet(commune_path))

    # Résumé
    logger.info("=== Traitement DPE terminé ===")
    logger.info(f"  Diagnostics individuels : {total:,}")
    logger.info(f"  Communes couvertes       : {commune_df.count():,}")
    logger.info("Distribution des classes énergie (toutes communes) :")
    df.groupBy("classe_energie").count().orderBy("classe_energie").show(truncate=False)
    logger.info("Distribution par source :")
    df.groupBy("source").count().show(truncate=False)

    df.unpersist()
    spark.stop()


# ── Entrée ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Traitement PySpark DPE (P2-2).")
    parser.add_argument("--raw-dir", default=str(RAW_DIR), help="Dossier source des CSV DPE.")
    parser.add_argument("--out-dir", default=str(OUT_DIR), help="Dossier de sortie Parquet.")
    args = parser.parse_args()

    run(Path(args.raw_dir), Path(args.out_dir))


if __name__ == "__main__":
    main()
