"""
Traitement PySpark des données BPE — Base Permanente des Équipements (P2-3).

Source : data/raw/bpe/bpe.csv (converti depuis BPE24.parquet via download_bpe.py)
  - CSV UTF-8, séparateur ;
  - Colonne DEPCOM : code commune INSEE (5 chars, clé de jointure)
  - Colonne TYPEQU : code type d'équipement (ex: A101=maternelle, D201=médecin)
  - ~1.8M équipements, ~35 000 communes

Étapes :
  1. Lecture du CSV BPE
  2. Normalisation code_commune (DEPCOM → 5 chars)
  3. Agrégation par commune :
     a. Comptage par grande catégorie (première lettre du TYPEQU) :
          A = Enseignement, B = Sport/Culture, C = Commerce,
          D = Santé, E = Transport, F = Tourisme
     b. Comptage de types clés pour l'évaluation immobilière
  4. Export Parquet → data/processed/bpe/commune_stats/

Codes TYPEQU de référence (INSEE — BPE 2024) :
  A101 = École maternelle         A104 = École élémentaire
  A111 = Crèche                   A203 = Collège
  A206 = Lycée général/techno     A207 = Lycée professionnel
  D101 = SAU (urgences)           D201 = Médecin généraliste
  D232 = Pharmacie                C101 = Hypermarché
  C201 = Supermarché              E102 = Gare ferroviaire

Usage :
    docker-compose run --rm processing python -m src.processing.spark_bpe
    docker-compose run --rm processing python -m src.processing.spark_bpe --raw-dir data/raw/bpe --out-dir data/processed/bpe
"""

import argparse
import logging
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from src.processing.spark_utils import build_local_friendly_spark_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/bpe")
OUT_DIR = Path("data/processed/bpe")

# ── Grandes catégories (première lettre du TYPEQU) ────────────────────────────
CATEGORIES = ["A", "B", "C", "D", "E", "F"]

# ── Types d'équipements clés pour l'évaluation immobilière ───────────────────
# Source : https://www.insee.fr/fr/metadonnees/source/serie/s1161
TYPEQU_CLES = {
    "nb_maternelles":  ["A101"],
    "nb_primaires":    ["A104"],
    "nb_creches":      ["A111"],
    "nb_colleges":     ["A203"],
    "nb_lycees":       ["A206", "A207"],
    "nb_medecins":     ["D201"],
    "nb_pharmacies":   ["D232"],
    "nb_urgences":     ["D101"],
    "nb_supermarches": ["C201"],
    "nb_hypermarches": ["C101"],
    "nb_gares":        ["E102"],
}

# ── Colonnes de sortie ────────────────────────────────────────────────────────
COMMUNE_STATS_OUTPUT_COLS = (
    ["code_commune", "nb_equipements_total"]
    + [f"nb_{cat.lower()}" for cat in CATEGORIES]  # nb_a, nb_b, …
    + list(TYPEQU_CLES.keys())
)


# ── SparkSession ──────────────────────────────────────────────────────────────


def build_spark_session(app_name: str = "spark_bpe") -> SparkSession:
    return build_local_friendly_spark_session(app_name, driver_memory="2g", shuffle_partitions="100")


# ── Lecture ───────────────────────────────────────────────────────────────────


def read_bpe(spark: SparkSession, raw_dir: Path) -> DataFrame:
    """
    Lit le CSV BPE (séparateur ;, encodage UTF-8).

    Le CSV est produit par _convert_parquet_to_csv() dans download_bpe.py.
    Les noms de colonnes viennent du Parquet INSEE — généralement en majuscules
    (DEPCOM, TYPEQU). On normalise ici pour les deux cas.
    """
    path = raw_dir / "bpe.csv"
    if not path.exists():
        raise FileNotFoundError(f"Fichier absent : {path}")

    logger.info(f"[BPE] Lecture : {path}")

    df = (
        spark.read
        .option("header", "true")
        .option("encoding", "UTF-8")
        .option("sep", ";")
        .option("inferSchema", "false")
        .csv(str(path))
    )

    logger.info(f"[BPE] Colonnes détectées : {df.columns}")

    # Normaliser les noms de colonnes (majuscules → minuscules)
    for col in df.columns:
        df = df.withColumnRenamed(col, col.lower())

    # DEPCOM → code_commune
    depcom_col = "depcom" if "depcom" in df.columns else _find_column(df.columns, ["depcom", "code_commune", "commune"])
    typequ_col = "typequ" if "typequ" in df.columns else _find_column(df.columns, ["typequ", "type_equip", "type_eq"])

    df = df.select(
        F.col(depcom_col).alias("code_commune"),
        F.col(typequ_col).alias("typequ"),
    )

    count = df.count()
    logger.info(f"[BPE] {count:,} équipements lus")
    return df


def _find_column(columns: list[str], candidates: list[str]) -> str:
    """Trouve le premier nom de colonne disponible parmi les candidats."""
    for c in candidates:
        if c in columns:
            return c
    raise ValueError(f"Aucune colonne trouvée parmi {candidates}. Disponibles : {columns}")


# ── Nettoyage ─────────────────────────────────────────────────────────────────


def normalize_code_commune(df: DataFrame) -> DataFrame:
    """S'assure que code_commune fait 5 chars (padding gauche avec 0)."""
    before = df.count()
    df = df.filter(F.col("code_commune").isNotNull() & (F.length(F.trim("code_commune")) > 0))
    df = df.withColumn("code_commune", F.lpad(F.trim("code_commune"), 5, "0"))
    removed = before - df.count()
    if removed:
        logger.info(f"[Code commune] {removed:,} lignes sans code commune supprimées")
    return df


def filter_typequ(df: DataFrame) -> DataFrame:
    """Conserve uniquement les lignes avec un TYPEQU valide (4-5 chars, commence par A-F)."""
    before = df.count()
    df = df.filter(
        F.col("typequ").isNotNull()
        & F.col("typequ").rlike("^[A-F][0-9]{2,3}$")
    )
    removed = before - df.count()
    if removed:
        logger.info(f"[Filtre TYPEQU] {removed:,} lignes avec code invalide supprimées")
    return df


# ── Agrégation ────────────────────────────────────────────────────────────────


def aggregate_by_commune(df: DataFrame) -> DataFrame:
    """
    Agrège les équipements par commune.

    Produit pour chaque commune :
      - nb_equipements_total : total tous types
      - nb_a … nb_f : total par grande catégorie (première lettre TYPEQU)
      - nb_maternelles, nb_medecins, … : types clés pour l'immobilier
    """
    logger.info("[Agrégation] Calcul des équipements par commune...")

    # Ajouter la colonne catégorie (première lettre du TYPEQU)
    df = df.withColumn("categorie", F.substring("typequ", 1, 1))

    agg_exprs = [
        F.count("*").alias("nb_equipements_total"),
    ]

    # Comptage par grande catégorie
    for cat in CATEGORIES:
        agg_exprs.append(
            F.sum(F.when(F.col("categorie") == cat, 1).otherwise(0)).alias(f"nb_{cat.lower()}")
        )

    # Comptage des types clés
    for col_name, codes in TYPEQU_CLES.items():
        agg_exprs.append(
            F.sum(F.when(F.col("typequ").isin(codes), 1).otherwise(0)).alias(col_name)
        )

    result = df.groupBy("code_commune").agg(*agg_exprs)

    count = result.count()
    logger.info(f"[Agrégation] {count:,} communes avec équipements BPE")
    return result


# ── Pipeline principal ────────────────────────────────────────────────────────


def run(raw_dir: Path, out_dir: Path) -> None:
    spark = build_spark_session()
    logger.info(f"SparkSession démarrée — master : {spark.conf.get('spark.master')}")

    # 1. Lecture
    df = read_bpe(spark, raw_dir)

    # 2. Nettoyage
    df = normalize_code_commune(df)
    df = filter_typequ(df)

    total = df.count()
    logger.info(f"[Pipeline] {total:,} équipements valides")

    # 3. Agrégation par commune
    commune_df = aggregate_by_commune(df)

    # 4. Export Parquet
    out_path = str(out_dir / "commune_stats")
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Export Parquet → {out_path}")
    (
        commune_df.select(*COMMUNE_STATS_OUTPUT_COLS)
        .write
        .mode("overwrite")
        .parquet(out_path)
    )

    # Résumé
    logger.info("=== Traitement BPE terminé ===")
    logger.info(f"  Équipements traités : {total:,}")
    logger.info(f"  Communes couvertes  : {commune_df.count():,}")
    logger.info("Top 5 communes par nb d'équipements :")
    commune_df.orderBy(F.col("nb_equipements_total").desc()).show(5, truncate=False)

    spark.stop()


# ── Entrée ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Traitement PySpark BPE (P2-3).")
    parser.add_argument("--raw-dir", default=str(RAW_DIR), help="Dossier source du CSV BPE.")
    parser.add_argument("--out-dir", default=str(OUT_DIR), help="Dossier de sortie Parquet.")
    args = parser.parse_args()

    run(Path(args.raw_dir), Path(args.out_dir))


if __name__ == "__main__":
    main()
