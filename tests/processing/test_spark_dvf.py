"""
Tests pour src/processing/spark_dvf.py.

Stratégie : PySpark est optionnel (groupe bigdata non installé en CI).
  - On teste toute la logique pure Python : constantes, seuils, mappings, colonnes.
  - Les transformations Spark sont testées via des mocks légers (MagicMock).
  - Un marker `pyspark` permet de lancer les tests d'intégration Spark séparément
    si pyspark est disponible : pytest -m pyspark
"""

import sys
from unittest.mock import MagicMock, patch, call
from pathlib import Path

import pytest

# ── Import conditionnel de pyspark ────────────────────────────────────────────
from tests.processing.conftest import PYSPARK_AVAILABLE

pyspark_only = pytest.mark.skipif(not PYSPARK_AVAILABLE, reason="pyspark non installé")

# ── Import du module sous test ────────────────────────────────────────────────
from src.processing.spark_dvf import (
    DGFIP_COL_MAP,
    OUTPUT_COLS,
    PRIX_M2_MAX,
    PRIX_M2_MIN,
    PRIX_MIN,
    SURFACE_MAX,
    SURFACE_MIN,
)
from src.ingestion.download_dvf import GEO_DVF_YEARS, DGFIP_YEARS


# ── Constantes et seuils ──────────────────────────────────────────────────────


def test_prix_m2_min_positif():
    assert PRIX_M2_MIN > 0


def test_prix_m2_max_superieur_min():
    assert PRIX_M2_MAX > PRIX_M2_MIN


def test_surface_min_positif():
    assert SURFACE_MIN > 0


def test_surface_max_superieur_min():
    assert SURFACE_MAX > SURFACE_MIN


def test_prix_min_positif():
    assert PRIX_MIN > 0


def test_seuils_realistes():
    """Les seuils doivent couvrir la réalité du marché immobilier français."""
    assert PRIX_M2_MIN <= 500        # logements très dégradés en zone rurale
    assert PRIX_M2_MAX >= 20_000     # Paris centre peut dépasser 15 000 €/m²
    assert SURFACE_MIN <= 9          # studio peut faire ~9 m²
    assert SURFACE_MAX >= 500        # grandes maisons/châteaux


# ── Plages d'années ───────────────────────────────────────────────────────────


def test_geo_dvf_years_contient_2020_a_2024():
    assert 2020 in GEO_DVF_YEARS
    assert 2024 in GEO_DVF_YEARS


def test_dgfip_years_contient_2014_a_2019():
    assert 2014 in DGFIP_YEARS
    assert 2019 in DGFIP_YEARS


def test_pas_de_chevauchement_annees():
    assert set(GEO_DVF_YEARS).isdisjoint(set(DGFIP_YEARS))


def test_geo_dvf_years_ordonnes():
    assert GEO_DVF_YEARS == sorted(GEO_DVF_YEARS)


def test_dgfip_years_ordonnes():
    assert DGFIP_YEARS == sorted(DGFIP_YEARS)


# ── Mapping colonnes DGFiP ────────────────────────────────────────────────────


def test_dgfip_col_map_contient_colonnes_critiques():
    """Les colonnes indispensables au pipeline doivent être dans le mapping."""
    required = [
        "Date mutation",
        "Nature mutation",
        "Valeur fonciere",
        "Code commune",
        "Code departement",
        "Type local",
        "Surface reelle bati",
        "Nombre pieces principales",
        "Surface terrain",
    ]
    for col in required:
        assert col in DGFIP_COL_MAP, f"Colonne manquante dans DGFIP_COL_MAP : '{col}'"


def test_dgfip_col_map_valeur_fonciere_raw():
    """La valeur foncière doit être nommée *_raw avant conversion décimale."""
    assert DGFIP_COL_MAP["Valeur fonciere"] == "valeur_fonciere_raw"


def test_dgfip_col_map_date_raw():
    """La date doit être nommée *_raw avant conversion de format."""
    assert DGFIP_COL_MAP["Date mutation"] == "date_mutation_raw"


def test_dgfip_col_map_code_commune_court():
    """code_commune DGFiP = 3 chars → doit être nommé _court pour rappeler qu'il faut le compléter."""
    assert DGFIP_COL_MAP["Code commune"] == "code_commune_court"


def test_dgfip_col_map_pas_de_doublons_valeurs():
    """Deux colonnes sources ne doivent pas pointer vers le même nom cible."""
    values = list(DGFIP_COL_MAP.values())
    assert len(values) == len(set(values)), "Doublons dans les valeurs de DGFIP_COL_MAP"


# ── Colonnes de sortie ────────────────────────────────────────────────────────


def test_output_cols_contient_colonnes_essentielles():
    essentielles = [
        "id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere",
        "code_commune", "type_local", "surface_reelle_bati", "prix_m2",
        "annee", "source",
    ]
    for col in essentielles:
        assert col in OUTPUT_COLS, f"Colonne manquante dans OUTPUT_COLS : '{col}'"


def test_output_cols_pas_de_doublons():
    assert len(OUTPUT_COLS) == len(set(OUTPUT_COLS))


def test_output_cols_contient_coordonnees():
    """Les coordonnées GPS sont nécessaires pour l'affichage carte."""
    assert "longitude" in OUTPUT_COLS
    assert "latitude" in OUTPUT_COLS


def test_output_cols_contient_annee():
    """annee est la clé de partition Parquet."""
    assert "annee" in OUTPUT_COLS


# ── build_spark_session ───────────────────────────────────────────────────────


def test_build_spark_session_utilise_local_par_defaut():
    """Sans SPARK_MASTER_URL, le master doit être local[*]."""
    from src.processing.spark_dvf import build_spark_session

    mock_builder = MagicMock()
    mock_builder.appName.return_value = mock_builder
    mock_builder.master.return_value = mock_builder
    mock_builder.config.return_value = mock_builder
    mock_builder.getOrCreate.return_value = MagicMock()

    with patch("src.processing.spark_dvf.SparkSession") as mock_spark_cls:
        mock_spark_cls.builder = mock_builder
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("SPARK_MASTER_URL", None)
            build_spark_session("test")
            mock_builder.master.assert_called_once_with("local[*]")


def test_build_spark_session_utilise_env_variable():
    """Avec SPARK_MASTER_URL défini, il doit être utilisé comme master."""
    from src.processing.spark_dvf import build_spark_session

    mock_builder = MagicMock()
    mock_builder.appName.return_value = mock_builder
    mock_builder.master.return_value = mock_builder
    mock_builder.config.return_value = mock_builder
    mock_builder.getOrCreate.return_value = MagicMock()

    with patch("src.processing.spark_dvf.SparkSession") as mock_spark_cls:
        mock_spark_cls.builder = mock_builder
        with patch.dict("os.environ", {"SPARK_MASTER_URL": "spark://master:7077"}):
            build_spark_session("test")
            mock_builder.master.assert_called_once_with("spark://master:7077")


# ── read_geo_dvf — vérification FileNotFoundError ────────────────────────────


def test_read_geo_dvf_leve_erreur_si_dossier_vide(tmp_path):
    """Si le dossier geo/ est vide, FileNotFoundError doit être levée."""
    from src.processing.spark_dvf import read_geo_dvf
    geo_dir = tmp_path / "geo"
    geo_dir.mkdir()

    mock_spark = MagicMock()
    with pytest.raises(FileNotFoundError, match="Aucun fichier Geo-DVF"):
        read_geo_dvf(mock_spark, tmp_path)


def test_read_dgfip_dvf_leve_erreur_si_dossier_vide(tmp_path):
    """Si le dossier dgfip/ est vide, FileNotFoundError doit être levée."""
    from src.processing.spark_dvf import read_dgfip_dvf
    dgfip_dir = tmp_path / "dgfip"
    dgfip_dir.mkdir()

    mock_spark = MagicMock()
    with pytest.raises(FileNotFoundError, match="Aucun fichier DVF DGFiP"):
        read_dgfip_dvf(mock_spark, tmp_path)


# ── Tests d'intégration Spark (nécessite pyspark installé) ───────────────────


@pyspark_only
class TestSparkDvfIntegration:
    """Tests d'intégration avec une vraie SparkSession locale."""

    @pytest.fixture(scope="class")
    def spark(self):
        session = SparkSession.builder.appName("test_dvf").master("local[1]").getOrCreate()
        session.sparkContext.setLogLevel("ERROR")
        yield session
        session.stop()

    def test_filter_ventes_conserve_uniquement_ventes(self, spark):
        from src.processing.spark_dvf import filter_ventes
        from pyspark.sql.types import StructType, StructField, StringType

        schema = StructType([StructField("nature_mutation", StringType(), True)])
        df = spark.createDataFrame(
            [("Vente",), ("Adjudication",), ("Vente",), ("Échange",)],
            schema,
        )
        result = filter_ventes(df)
        natures = [r.nature_mutation for r in result.collect()]
        assert all(n == "Vente" for n in natures)
        assert len(natures) == 2

    def test_filter_type_local_conserve_maison_appartement(self, spark):
        from src.processing.spark_dvf import filter_type_local
        from pyspark.sql.types import StructType, StructField, StringType

        schema = StructType([StructField("type_local", StringType(), True)])
        df = spark.createDataFrame(
            [("Maison",), ("Appartement",), ("Dépendance",), ("Local industriel. commercial ou assimilé",)],
            schema,
        )
        result = filter_type_local(df)
        types = [r.type_local for r in result.collect()]
        assert set(types) == {"Maison", "Appartement"}

    def test_normalize_code_commune_padde_a_5_chars(self, spark):
        from src.processing.spark_dvf import normalize_code_commune
        from pyspark.sql.types import StructType, StructField, StringType

        schema = StructType([StructField("code_commune", StringType(), True)])
        df = spark.createDataFrame([("75056",), ("1001",), ("13055",)], schema)
        result = normalize_code_commune(df)
        codes = [r.code_commune for r in result.collect()]
        assert all(len(c) == 5 for c in codes)
        assert "01001" in codes

    def test_compute_prix_m2_calcul_correct(self, spark):
        from src.processing.spark_dvf import compute_prix_m2
        from pyspark.sql.types import StructType, StructField, DoubleType

        schema = StructType([
            StructField("valeur_fonciere", DoubleType(), True),
            StructField("surface_reelle_bati", DoubleType(), True),
        ])
        df = spark.createDataFrame([(200_000.0, 50.0), (300_000.0, 0.0), (150_000.0, None)], schema)
        result = compute_prix_m2(df)
        rows = {(r.valeur_fonciere, r.surface_reelle_bati): r.prix_m2 for r in result.collect()}

        assert rows[(200_000.0, 50.0)] == pytest.approx(4000.0)
        assert rows[(300_000.0, 0.0)] is None   # surface nulle → None
        assert rows[(150_000.0, None)] is None  # surface None → None

    def test_filter_anomalies_supprime_valeurs_aberrantes(self, spark):
        from src.processing.spark_dvf import compute_prix_m2, filter_anomalies
        from pyspark.sql.types import StructType, StructField, DoubleType

        schema = StructType([
            StructField("valeur_fonciere", DoubleType(), True),
            StructField("surface_reelle_bati", DoubleType(), True),
            StructField("prix_m2", DoubleType(), True),
        ])
        df = spark.createDataFrame([
            (200_000.0, 50.0, 4_000.0),     # OK
            (500.0, 50.0, 10.0),             # prix trop bas → exclu
            (200_000.0, 3.0, 66_000.0),      # surface trop petite → exclu
            (200_000.0, 50.0, 200_000.0),    # prix/m² trop élevé → exclu
        ], schema)
        result = filter_anomalies(df)
        assert result.count() == 1

    def test_add_annee_extrait_annee_de_date(self, spark):
        from src.processing.spark_dvf import add_annee
        from pyspark.sql import functions as F
        from pyspark.sql.types import StructType, StructField, DateType, StringType
        import datetime

        schema = StructType([StructField("date_mutation", DateType(), True)])
        df = spark.createDataFrame(
            [(datetime.date(2022, 6, 15),), (datetime.date(2019, 1, 1),)],
            schema,
        )
        result = add_annee(df)
        annees = sorted([r.annee for r in result.collect()])
        assert annees == [2019, 2022]
