"""
Traitement PySpark des données DVF — Demandes de Valeurs Foncières (P2-1).

Fusionne et nettoie 2 sources de formats différents :
  - Geo-DVF (Etalab, 2020-2024) : data/raw/dvf/geo/dvf_YYYY.csv
      CSV UTF-8, séparateur virgule, avec id_mutation et coordonnées GPS
  - DVF brut (DGFiP, 2014-2019)  : data/raw/dvf/dgfip/dvf_YYYY.csv
      CSV Latin-1, séparateur |, code_commune sur 3 chars, date JJ/MM/AAAA

Étapes :
  1. Lecture des fichiers CSV de chaque source avec schémas explicites
  2. Normalisation du DVF brut DGFiP (colonnes, types, code_commune)
  3. Union des deux sources sur colonnes communes
  4. Filtres : "Vente" uniquement, Maison/Appartement uniquement
  5. Déduplication des mutations multi-lots (agrégation par id_mutation)
  6. Calcul prix_m2 = valeur_fonciere / surface_reelle_bati
  7. Filtrage des anomalies (valeurs aberrantes)
  8. Ajout colonne annee depuis date_mutation
  9. Export Parquet partitionné par annee

Sorties (data/processed/dvf/) :
  - Parquet partitionné par annee=YYYY/
  - ~25-30M lignes brutes → ~8-12M lignes après nettoyage

Usage :
    docker-compose run --rm processing python -m src.processing.spark_dvf
    docker-compose run --rm processing python -m src.processing.spark_dvf --raw-dir data/raw/dvf --out-dir data/processed/dvf
"""

import argparse
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/dvf")
OUT_DIR = Path("data/processed/dvf")

# ── Seuils de filtrage des anomalies ─────────────────────────────────────────
PRIX_M2_MIN = 100  # €/m² — en dessous = erreur de saisie ou donation déguisée
PRIX_M2_MAX = 100_000  # €/m² — au-dessus = bien exceptionnel ou erreur
SURFACE_MIN = 5  # m² — en dessous = non physique
SURFACE_MAX = 10_000  # m² — au-dessus = probable erreur
PRIX_MIN = 1_000  # € — ventes symboliques exclues

# ── Colonnes de sortie (communes aux deux sources) ────────────────────────────
# Colonnes absentes dans le DVF brut DGFiP → remplies avec null
OUTPUT_COLS = [
    "id_mutation",  # str  | null pour DGFiP
    "date_mutation",  # date
    "nature_mutation",  # str
    "valeur_fonciere",  # double (€)
    "code_commune",  # str  5 chars (clé de jointure)
    "type_local",  # str  "Maison" | "Appartement"
    "surface_reelle_bati",  # double (m²) — somme si multi-lots
    "nombre_pieces_principales",  # int — valeur du lot principal
    "surface_terrain",  # double (m²) — somme si multi-lots
    "longitude",  # double | null pour DGFiP
    "latitude",  # double | null pour DGFiP
    "annee",  # int  — extrait de date_mutation
    "prix_m2",  # double — calculé
    "source",  # str  "geo" | "dgfip"
]


# ── SparkSession ──────────────────────────────────────────────────────────────


def build_spark_session(app_name: str = "spark_dvf") -> SparkSession:
    return build_local_friendly_spark_session(app_name, driver_memory="4g", shuffle_partitions="200")


# ── Schémas explicites ────────────────────────────────────────────────────────
# Les schémas explicites évitent que Spark infère les types (code_commune
# "01001" serait lu comme entier 1001 en inférence automatique).

GEO_DVF_SCHEMA = StructType(
    [
        StructField("id_mutation", StringType(), True),
        StructField("date_mutation", StringType(), True),  # lire en str, convertir ensuite
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

# DVF brut DGFiP : colonnes avec espaces dans les noms réels
# On les renomme immédiatement après lecture.
DGFIP_COL_MAP = {
    "No disposition": "numero_disposition",
    "Date mutation": "date_mutation_raw",  # JJ/MM/AAAA → converti
    "Nature mutation": "nature_mutation",
    "Valeur fonciere": "valeur_fonciere_raw",  # virgule comme décimal
    "Code voie": "adresse_code_voie",
    "Voie": "adresse_nom_voie",
    "Code postal": "code_postal",
    "Commune": "nom_commune",
    "Code departement": "code_departement",
    "Code commune": "code_commune_court",  # 3 chars → padded + prefixé
    "Nombre de lots": "nombre_lots",
    "Code type local": "code_type_local",
    "Type local": "type_local",
    "Surface reelle bati": "surface_reelle_bati",
    "Nombre pieces principales": "nombre_pieces_principales",
    "Nature culture": "nature_culture",
    "Nature culture speciale": "nature_culture_speciale",
    "Surface terrain": "surface_terrain",
}


# ── Lecture ───────────────────────────────────────────────────────────────────


def read_geo_dvf(spark: SparkSession, raw_dir: Path) -> DataFrame:
    """
    Lit tous les fichiers Geo-DVF Etalab (2020-2024).
    Ajoute une colonne source='geo' et convertit date_mutation en DateType.
    """
    geo_dir = raw_dir / "geo"
    csv_files = sorted(geo_dir.glob("dvf_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"Aucun fichier Geo-DVF trouvé dans {geo_dir}")

    logger.info(f"[Geo-DVF] Lecture de {len(csv_files)} fichier(s) : {[f.name for f in csv_files]}")

    df = (
        spark.read.option("header", "true")
        .option("encoding", "UTF-8")
        .option("sep", ",")
        .schema(GEO_DVF_SCHEMA)
        .csv([str(f) for f in csv_files])
    )

    df = df.withColumn("date_mutation", F.to_date("date_mutation", "yyyy-MM-dd"))
    df = df.withColumn("source", F.lit("geo"))
    logger.info(f"[Geo-DVF] {df.count():,} lignes lues")
    return df


def read_dgfip_dvf(spark: SparkSession, raw_dir: Path) -> DataFrame:
    """
    Lit tous les fichiers DVF brut DGFiP (2014-2019), encodage Latin-1, séparateur |.
    Normalise les colonnes pour les aligner sur le schéma Geo-DVF.
    """
    dgfip_dir = raw_dir / "dgfip"
    csv_files = sorted(dgfip_dir.glob("dvf_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"Aucun fichier DVF DGFiP trouvé dans {dgfip_dir}")

    logger.info(f"[DGFiP] Lecture de {len(csv_files)} fichier(s) : {[f.name for f in csv_files]}")

    df = (
        spark.read.option("header", "true")
        .option("encoding", "ISO-8859-1")
        .option("sep", "|")
        .option("inferSchema", "false")  # tout en string, on convertit manuellement
        .csv([str(f) for f in csv_files])
    )

    # Renommer les colonnes (noms avec espaces → noms normalisés)
    for raw_name, clean_name in DGFIP_COL_MAP.items():
        if raw_name in df.columns:
            df = df.withColumnRenamed(raw_name, clean_name)

    # Convertir valeur_fonciere : virgule décimale → point décimale
    df = df.withColumn(
        "valeur_fonciere",
        F.regexp_replace("valeur_fonciere_raw", ",", ".").cast(DoubleType()),
    ).drop("valeur_fonciere_raw")

    # Convertir date_mutation : JJ/MM/AAAA → DateType
    df = df.withColumn(
        "date_mutation",
        F.to_date("date_mutation_raw", "dd/MM/yyyy"),
    ).drop("date_mutation_raw")

    # Reconstruire code_commune sur 5 chars :
    # code_departement (2 chars) + code_commune_court (3 chars, padded à gauche)
    df = df.withColumn(
        "code_commune",
        F.concat(
            F.col("code_departement"),
            F.lpad(F.col("code_commune_court"), 3, "0"),
        ),
    ).drop("code_commune_court")

    # Convertir surfaces et pièces en numérique
    df = df.withColumn("surface_reelle_bati", F.col("surface_reelle_bati").cast(DoubleType()))
    df = df.withColumn("surface_terrain", F.col("surface_terrain").cast(DoubleType()))
    df = df.withColumn("nombre_pieces_principales", F.col("nombre_pieces_principales").cast(IntegerType()))

    # Colonnes absentes dans DGFiP → null
    df = df.withColumn("id_mutation", F.lit(None).cast(StringType()))
    df = df.withColumn("longitude", F.lit(None).cast(DoubleType()))
    df = df.withColumn("latitude", F.lit(None).cast(DoubleType()))
    df = df.withColumn("source", F.lit("dgfip"))

    logger.info(f"[DGFiP] {df.count():,} lignes lues")
    return df


# ── Transformations ───────────────────────────────────────────────────────────


def filter_ventes(df: DataFrame) -> DataFrame:
    """Conserve uniquement les mutations de type 'Vente'."""
    before = df.count()
    df = df.filter(F.col("nature_mutation") == "Vente")
    logger.info(f"[Filtre ventes] {before:,} → {df.count():,} lignes")
    return df


def filter_type_local(df: DataFrame) -> DataFrame:
    """Conserve uniquement Maison et Appartement (exclut terrains, locaux commerciaux…)."""
    before = df.count()
    df = df.filter(F.col("type_local").isin("Maison", "Appartement"))
    logger.info(f"[Filtre type_local] {before:,} → {df.count():,} lignes")
    return df


def normalize_code_commune(df: DataFrame) -> DataFrame:
    """
    S'assure que code_commune fait bien 5 chars.
    Geo-DVF les fournit déjà à 5 chars mais certains cas limites peuvent arriver.
    """
    return df.withColumn(
        "code_commune",
        F.lpad(F.col("code_commune"), 5, "0"),
    )


def deduplicate_mutations(df: DataFrame) -> DataFrame:
    """
    Déduplique les mutations multi-lots : une mutation = une transaction unique.

    Problème : en DVF, un appartement + une cave dans le même immeuble = 2 lignes
    avec le même id_mutation et la même valeur_fonciere. Il faut :
      - Sommer les surfaces (surface_reelle_bati, surface_terrain)
      - Garder la première valeur pour les autres colonnes (valeur_fonciere identique,
        type_local du lot principal, etc.)

    Pour le DVF DGFiP (sans id_mutation) : on groupe par les champs identifiants
    disponibles (date_mutation, valeur_fonciere, code_commune, type_local).
    """
    logger.info("[Déduplication] Début — agrégation des mutations multi-lots...")

    # ── Geo-DVF : déduplication par id_mutation ───────────────────────────────
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

    # ── DVF DGFiP : déduplication par clé composite ───────────────────────────
    # Sans id_mutation, on groupe sur les champs qui identifient une transaction
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


def compute_prix_m2(df: DataFrame) -> DataFrame:
    """Calcule prix_m2 = valeur_fonciere / surface_reelle_bati."""
    return df.withColumn(
        "prix_m2",
        F.when(
            F.col("surface_reelle_bati") > 0,
            F.round(F.col("valeur_fonciere") / F.col("surface_reelle_bati"), 2),
        ).otherwise(F.lit(None).cast(DoubleType())),
    )


def filter_anomalies(df: DataFrame) -> DataFrame:
    """
    Filtre les valeurs aberrantes :
    - prix négatif ou nul
    - surface nulle ou aberrante
    - prix/m² hors bornes réalistes
    """
    before = df.count()
    df = df.filter(
        (F.col("valeur_fonciere") >= PRIX_MIN)
        & (F.col("surface_reelle_bati") >= SURFACE_MIN)
        & (F.col("surface_reelle_bati") <= SURFACE_MAX)
        & (F.col("prix_m2") >= PRIX_M2_MIN)
        & (F.col("prix_m2") <= PRIX_M2_MAX)
    )
    removed = before - df.count()
    logger.info(f"[Anomalies] {removed:,} lignes supprimées  ({removed / before * 100:.1f}%)")
    return df


def add_annee(df: DataFrame) -> DataFrame:
    """Ajoute la colonne annee (int) extraite de date_mutation."""
    return df.withColumn("annee", F.year("date_mutation").cast(IntegerType()))


# ── Pipeline principal ────────────────────────────────────────────────────────


def run(raw_dir: Path, out_dir: Path) -> None:
    spark = build_spark_session()
    logger.info(f"SparkSession démarrée — master : {spark.conf.get('spark.master')}")

    # 1. Lecture
    geo_df = read_geo_dvf(spark, raw_dir)
    dgfip_df = read_dgfip_dvf(spark, raw_dir)

    # Sélectionner les colonnes communes avant union
    common_cols = [
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
    geo_df = geo_df.select(*common_cols)
    dgfip_df = dgfip_df.select(*common_cols)

    # 2. Union
    df = geo_df.unionByName(dgfip_df)
    logger.info(f"[Union] Total : {df.count():,} lignes")

    # 3. Filtres initiaux
    df = filter_ventes(df)
    df = filter_type_local(df)

    # 4. Normalisation code_commune
    df = normalize_code_commune(df)

    # 5. Déduplication mutations multi-lots
    df = deduplicate_mutations(df)

    # 6. Calcul prix_m2
    df = compute_prix_m2(df)

    # 7. Filtrage anomalies
    df = filter_anomalies(df)

    # 8. Ajout annee
    df = add_annee(df)

    # 9. Sélection finale + export Parquet partitionné par annee
    df = df.select(*OUTPUT_COLS)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(out_dir)
    logger.info(f"Export Parquet → {out_path}  (partitionné par annee)")

    (df.write.mode("overwrite").partitionBy("annee").parquet(out_path))

    # Résumé
    total = df.count()
    logger.info(f"=== Traitement DVF terminé : {total:,} transactions nettes ===")
    logger.info("Distribution par année :")
    df.groupBy("annee").count().orderBy("annee").show(truncate=False)
    logger.info("Distribution par type_local :")
    df.groupBy("type_local").count().orderBy("type_local").show(truncate=False)

    spark.stop()


# ── Entrée ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Traitement PySpark DVF (P2-1).")
    parser.add_argument("--raw-dir", default=str(RAW_DIR), help="Dossier source des CSV DVF.")
    parser.add_argument("--out-dir", default=str(OUT_DIR), help="Dossier de sortie Parquet.")
    args = parser.parse_args()

    run(Path(args.raw_dir), Path(args.out_dir))


if __name__ == "__main__":
    main()
