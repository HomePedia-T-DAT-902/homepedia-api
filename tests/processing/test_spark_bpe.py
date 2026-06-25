"""
Tests pour src/processing/spark_bpe.py.

Même stratégie que test_spark_dpe.py :
  - Logique pure Python sans PySpark : constantes, _find_column, etc.
  - Tests d'intégration Spark marqués @pyspark_only (skip si pyspark absent).
"""

from unittest.mock import MagicMock, patch

import pytest

from tests.processing.conftest import PYSPARK_AVAILABLE

# Vérifie que PySpark est installé ET que la SparkSession peut réellement démarrer
# (Java 23 peut bloquer même si pyspark est importable)
_SPARK_FUNCTIONAL = False
if PYSPARK_AVAILABLE:
    try:
        from pyspark.sql import SparkSession as _SS
        _s = (
            _SS.builder
            .appName("probe")
            .master("local[1]")
            .config("spark.ui.enabled", "false")
            .getOrCreate()
        )
        # Test that actual computation works (count triggers JVM execution)
        _s.createDataFrame([(1,)], ["x"]).count()
        _s.stop()
        _SPARK_FUNCTIONAL = True
    except Exception:
        pass

pyspark_only = pytest.mark.skipif(
    not _SPARK_FUNCTIONAL,
    reason="pyspark non fonctionnel (non installé ou incompatibilité Java)",
)

from src.processing.spark_bpe import (
    CATEGORIES,
    COMMUNE_STATS_OUTPUT_COLS,
    TYPEQU_CLES,
    _find_column,
)


# ── Constantes ────────────────────────────────────────────────────────────────


def test_categories_contient_domaines_essentiels():
    """Les 6 grandes catégories INSEE doivent toutes être présentes."""
    for cat in ["A", "B", "C", "D", "E", "F"]:
        assert cat in CATEGORIES


def test_typequ_cles_contient_equipements_immobilier():
    """Les équipements clés pour l'immobilier doivent être définis."""
    essentiels = ["nb_maternelles", "nb_medecins", "nb_pharmacies", "nb_gares"]
    for eq in essentiels:
        assert eq in TYPEQU_CLES, f"Équipement manquant dans TYPEQU_CLES : '{eq}'"


def test_typequ_cles_codes_format():
    """Chaque code TYPEQU doit faire 4 chars (lettre + 3 chiffres)."""
    for col_name, codes in TYPEQU_CLES.items():
        assert isinstance(codes, list), f"{col_name} doit être une liste"
        assert len(codes) > 0, f"{col_name} ne doit pas être vide"
        for code in codes:
            assert len(code) == 4, f"Code '{code}' dans {col_name} doit faire 4 chars"
            assert code[0].isalpha(), f"Code '{code}' doit commencer par une lettre"
            assert code[1:].isdigit(), f"Code '{code}' doit finir par 3 chiffres"


# ── Colonnes de sortie ────────────────────────────────────────────────────────


def test_commune_stats_output_cols_contient_code_commune():
    assert "code_commune" in COMMUNE_STATS_OUTPUT_COLS


def test_commune_stats_output_cols_contient_total():
    assert "nb_equipements_total" in COMMUNE_STATS_OUTPUT_COLS


def test_commune_stats_output_cols_contient_toutes_categories():
    for cat in CATEGORIES:
        assert f"nb_{cat.lower()}" in COMMUNE_STATS_OUTPUT_COLS


def test_commune_stats_output_cols_contient_types_cles():
    for col_name in TYPEQU_CLES:
        assert col_name in COMMUNE_STATS_OUTPUT_COLS, f"Colonne manquante : '{col_name}'"


def test_commune_stats_output_cols_pas_de_doublons():
    assert len(COMMUNE_STATS_OUTPUT_COLS) == len(set(COMMUNE_STATS_OUTPUT_COLS))


# ── _find_column ──────────────────────────────────────────────────────────────


def test_find_column_trouve_premier_candidat():
    assert _find_column(["depcom", "typequ", "nb_equip"], ["depcom", "commune"]) == "depcom"


def test_find_column_trouve_candidat_suivant_si_premier_absent():
    assert _find_column(["commune", "typequ"], ["depcom", "commune"]) == "commune"


def test_find_column_leve_erreur_si_aucun_candidat():
    with pytest.raises(ValueError, match="Aucune colonne trouvée"):
        _find_column(["foo", "bar"], ["depcom", "commune"])


def test_find_column_message_erreur_liste_disponibles():
    with pytest.raises(ValueError, match="Disponibles"):
        _find_column(["col1", "col2"], ["depcom"])


# ── read_bpe — FileNotFoundError ──────────────────────────────────────────────


def test_read_bpe_leve_erreur_si_fichier_absent(tmp_path):
    from src.processing.spark_bpe import read_bpe
    mock_spark = MagicMock()
    with pytest.raises(FileNotFoundError):
        read_bpe(mock_spark, tmp_path)


# ── build_spark_session ───────────────────────────────────────────────────────


def test_build_spark_session_local_par_defaut():
    from src.processing.spark_bpe import build_spark_session

    mock_builder = MagicMock()
    mock_builder.appName.return_value = mock_builder
    mock_builder.master.return_value = mock_builder
    mock_builder.config.return_value = mock_builder
    mock_builder.getOrCreate.return_value = MagicMock()

    with patch("src.processing.spark_utils.SparkSession") as mock_spark_cls:
        mock_spark_cls.builder = mock_builder
        import os
        os.environ.pop("SPARK_MASTER_URL", None)
        build_spark_session("test")
        mock_builder.master.assert_called_once_with("local[*]")


def test_build_spark_session_utilise_env():
    from src.processing.spark_bpe import build_spark_session

    mock_builder = MagicMock()
    mock_builder.appName.return_value = mock_builder
    mock_builder.master.return_value = mock_builder
    mock_builder.config.return_value = mock_builder
    mock_builder.getOrCreate.return_value = MagicMock()

    with patch("src.processing.spark_utils.SparkSession") as mock_spark_cls:
        mock_spark_cls.builder = mock_builder
        with patch.dict("os.environ", {"SPARK_MASTER_URL": "spark://master:7077"}):
            build_spark_session("test")
            mock_builder.master.assert_called_once_with("spark://master:7077")


# ── Tests d'intégration Spark ─────────────────────────────────────────────────


@pyspark_only
class TestSparkBpeIntegration:
    """Tests d'intégration avec une vraie SparkSession locale."""

    @pytest.fixture(scope="class")
    def spark(self):
        from pyspark.sql import SparkSession
        session = SparkSession.builder.appName("test_bpe").master("local[1]").getOrCreate()
        session.sparkContext.setLogLevel("ERROR")
        yield session
        session.stop()

    def test_normalize_code_commune_padde_5_chars(self, spark):
        from src.processing.spark_bpe import normalize_code_commune
        from pyspark.sql.types import StructType, StructField, StringType

        schema = StructType([
            StructField("code_commune", StringType(), True),
            StructField("typequ", StringType(), True),
        ])
        df = spark.createDataFrame([
            ("75056", "A101"),
            ("1001",  "D201"),
            (" 2A004 ", "E102"),
        ], schema)
        result = normalize_code_commune(df)
        codes = [r.code_commune for r in result.collect()]
        assert "01001" in codes
        assert all(len(c) == 5 for c in codes)

    def test_normalize_code_commune_exclut_nulls(self, spark):
        from src.processing.spark_bpe import normalize_code_commune
        from pyspark.sql.types import StructType, StructField, StringType

        schema = StructType([
            StructField("code_commune", StringType(), True),
            StructField("typequ", StringType(), True),
        ])
        df = spark.createDataFrame([
            ("75056", "A101"),
            (None,    "D201"),
            ("",      "C201"),
        ], schema)
        result = normalize_code_commune(df)
        assert result.count() == 1

    def test_filter_typequ_conserve_codes_valides(self, spark):
        from src.processing.spark_bpe import filter_typequ
        from pyspark.sql.types import StructType, StructField, StringType

        schema = StructType([
            StructField("code_commune", StringType(), True),
            StructField("typequ", StringType(), True),
        ])
        df = spark.createDataFrame([
            ("75056", "A101"),   # valide
            ("75056", "D201"),   # valide
            ("75056", "Z999"),   # invalide (Z hors A-F)
            ("75056", None),     # null → exclu
            ("75056", "A1"),     # trop court → exclu
            ("75056", "E102"),   # valide
        ], schema)
        result = filter_typequ(df)
        codes = [r.typequ for r in result.collect()]
        assert sorted(codes) == ["A101", "D201", "E102"]

    def test_aggregate_by_commune_total(self, spark):
        from src.processing.spark_bpe import aggregate_by_commune
        from pyspark.sql.types import StructType, StructField, StringType

        schema = StructType([
            StructField("code_commune", StringType(), True),
            StructField("typequ", StringType(), True),
        ])
        df = spark.createDataFrame([
            ("75056", "A101"),
            ("75056", "A101"),
            ("75056", "D201"),
            ("13055", "C201"),
        ], schema)
        result = aggregate_by_commune(df)
        rows = {r.code_commune: r for r in result.collect()}

        assert rows["75056"].nb_equipements_total == 3
        assert rows["13055"].nb_equipements_total == 1

    def test_aggregate_by_commune_categories(self, spark):
        from src.processing.spark_bpe import aggregate_by_commune
        from pyspark.sql.types import StructType, StructField, StringType

        schema = StructType([
            StructField("code_commune", StringType(), True),
            StructField("typequ", StringType(), True),
        ])
        df = spark.createDataFrame([
            ("75056", "A101"),  # catégorie A
            ("75056", "A104"),  # catégorie A
            ("75056", "D201"),  # catégorie D
            ("75056", "C201"),  # catégorie C
        ], schema)
        result = aggregate_by_commune(df)
        paris = [r for r in result.collect() if r.code_commune == "75056"][0]

        assert paris.nb_a == 2
        assert paris.nb_d == 1
        assert paris.nb_c == 1
        assert paris.nb_b == 0

    def test_aggregate_by_commune_types_cles(self, spark):
        from src.processing.spark_bpe import aggregate_by_commune
        from pyspark.sql.types import StructType, StructField, StringType

        schema = StructType([
            StructField("code_commune", StringType(), True),
            StructField("typequ", StringType(), True),
        ])
        df = spark.createDataFrame([
            ("75056", "A101"),  # maternelle
            ("75056", "A101"),  # maternelle
            ("75056", "D201"),  # médecin
            ("75056", "E102"),  # gare
        ], schema)
        result = aggregate_by_commune(df)
        paris = [r for r in result.collect() if r.code_commune == "75056"][0]

        assert paris.nb_maternelles == 2
        assert paris.nb_medecins == 1
        assert paris.nb_gares == 1
        assert paris.nb_pharmacies == 0
