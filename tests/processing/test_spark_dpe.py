"""
Tests pour src/processing/spark_dpe.py.

Même stratégie que test_spark_dvf.py :
  - Logique pure Python sans PySpark : constantes, _find_conso_column_nouveau, etc.
  - Tests d'intégration Spark marqués @pyspark_only (skip si pyspark absent).
"""

from unittest.mock import MagicMock, patch

import pytest

from tests.processing.conftest import PYSPARK_AVAILABLE

pyspark_only = pytest.mark.skipif(not PYSPARK_AVAILABLE, reason="pyspark non installé")

from src.processing.spark_dpe import (
    CLASSES_VALIDES,
    CONSO_MAX,
    CONSO_MIN,
    COMMUNE_STATS_OUTPUT_COLS,
    DIAG_OUTPUT_COLS,
    _find_conso_column_nouveau,
)


# ── Constantes ────────────────────────────────────────────────────────────────


def test_classes_valides_sont_a_a_g():
    assert CLASSES_VALIDES == {"A", "B", "C", "D", "E", "F", "G"}


def test_conso_min_est_zero():
    assert CONSO_MIN == 0


def test_conso_max_realiste():
    """Le max doit couvrir les passoires thermiques les plus énergivores (~900 kWh/m²/an)."""
    assert CONSO_MAX >= 900


def test_conso_max_exclut_aberrations():
    """Le max doit exclure les erreurs de saisie (ex: 50 000 kWh/m²/an)."""
    assert CONSO_MAX < 10_000


# ── Colonnes de sortie ────────────────────────────────────────────────────────


def test_diag_output_cols_contient_colonnes_essentielles():
    essentiels = ["code_commune", "date_diagnostic", "classe_energie", "consommation_moyenne", "source"]
    for col in essentiels:
        assert col in DIAG_OUTPUT_COLS, f"Colonne manquante dans DIAG_OUTPUT_COLS : '{col}'"


def test_commune_stats_output_cols_contient_toutes_classes():
    for classe in ["a", "b", "c", "d", "e", "f", "g"]:
        assert f"nb_classe_{classe}" in COMMUNE_STATS_OUTPUT_COLS
        assert f"pct_classe_{classe}" in COMMUNE_STATS_OUTPUT_COLS


def test_commune_stats_output_cols_contient_totaux():
    assert "nb_dpe_total" in COMMUNE_STATS_OUTPUT_COLS
    assert "consommation_moyenne_commune" in COMMUNE_STATS_OUTPUT_COLS
    assert "code_commune" in COMMUNE_STATS_OUTPUT_COLS


def test_diag_output_cols_pas_de_doublons():
    assert len(DIAG_OUTPUT_COLS) == len(set(DIAG_OUTPUT_COLS))


def test_commune_stats_output_cols_pas_de_doublons():
    assert len(COMMUNE_STATS_OUTPUT_COLS) == len(set(COMMUNE_STATS_OUTPUT_COLS))


# ── _find_conso_column_nouveau ────────────────────────────────────────────────


def _make_mock_df(columns: list[str]) -> MagicMock:
    """Crée un mock de DataFrame Spark avec la liste de colonnes donnée."""
    mock = MagicMock()
    mock.columns = columns
    return mock


def test_find_conso_column_trouve_nom_avec_espace():
    """Le nom original du dataset ADEME contient un espace."""
    df = _make_mock_df(["code_insee_ban", "conso_5 usages_par_m2_ef", "etiquette_dpe"])
    col = _find_conso_column_nouveau(df)
    assert col == "conso_5 usages_par_m2_ef"


def test_find_conso_column_trouve_nom_sans_espace():
    """Variante sans espace (certaines versions du dataset)."""
    df = _make_mock_df(["code_insee_ban", "conso_5_usages_par_m2_ef", "etiquette_dpe"])
    col = _find_conso_column_nouveau(df)
    assert col == "conso_5_usages_par_m2_ef"


def test_find_conso_column_insensible_a_la_casse():
    """La détection doit être insensible à la casse."""
    df = _make_mock_df(["CONSO_5 USAGES_PAR_M2_EF"])
    col = _find_conso_column_nouveau(df)
    assert col == "CONSO_5 USAGES_PAR_M2_EF"


def test_find_conso_column_leve_erreur_si_absente():
    df = _make_mock_df(["code_insee_ban", "etiquette_dpe", "date_etablissement_dpe"])
    with pytest.raises(ValueError, match="Colonne de consommation introuvable"):
        _find_conso_column_nouveau(df)


def test_find_conso_column_retourne_premier_match():
    """Si plusieurs colonnes matchent, retourne la première trouvée."""
    df = _make_mock_df(["conso_5 usages_par_m2_ef", "conso_5_usages_par_m2_ef"])
    col = _find_conso_column_nouveau(df)
    # L'une ou l'autre est valide, l'important est qu'elle contient conso_5 et par_m2_ef
    assert "conso_5" in col.lower() and "par_m2_ef" in col.lower()


# ── read_dpe_nouveau / read_dpe_ancien — FileNotFoundError ───────────────────


def test_read_dpe_nouveau_leve_erreur_si_fichier_absent(tmp_path):
    from src.processing.spark_dpe import read_dpe_nouveau
    mock_spark = MagicMock()
    with pytest.raises(FileNotFoundError):
        read_dpe_nouveau(mock_spark, tmp_path)


def test_read_dpe_ancien_leve_erreur_si_fichier_absent(tmp_path):
    from src.processing.spark_dpe import read_dpe_ancien
    mock_spark = MagicMock()
    with pytest.raises(FileNotFoundError):
        read_dpe_ancien(mock_spark, tmp_path)


# ── build_spark_session ───────────────────────────────────────────────────────


def test_build_spark_session_local_par_defaut():
    from src.processing.spark_dpe import build_spark_session

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
    from src.processing.spark_dpe import build_spark_session

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
class TestSparkDpeIntegration:
    """Tests d'intégration avec une vraie SparkSession locale."""

    @pytest.fixture(scope="class")
    def spark(self):
        session = SparkSession.builder.appName("test_dpe").master("local[1]").getOrCreate()
        session.sparkContext.setLogLevel("ERROR")
        yield session
        session.stop()

    def test_normalize_classe_energie_majuscule(self, spark):
        from src.processing.spark_dpe import normalize_classe_energie
        from pyspark.sql.types import StructType, StructField, StringType

        schema = StructType([StructField("classe_energie", StringType(), True)])
        df = spark.createDataFrame([("a",), ("B",), (" c ",), ("X",), ("G",)], schema)
        result = normalize_classe_energie(df)
        classes = sorted([r.classe_energie for r in result.collect()])
        assert classes == ["B", "C", "G"]

    def test_normalize_classe_energie_exclut_invalides(self, spark):
        from src.processing.spark_dpe import normalize_classe_energie
        from pyspark.sql.types import StructType, StructField, StringType

        schema = StructType([StructField("classe_energie", StringType(), True)])
        # H, X, N ne sont pas des classes DPE valides
        df = spark.createDataFrame([("A",), ("H",), ("X",), ("N",), ("G",)], schema)
        result = normalize_classe_energie(df)
        classes = sorted([r.classe_energie for r in result.collect()])
        assert classes == ["A", "G"]

    def test_normalize_code_commune_padde_5_chars(self, spark):
        from src.processing.spark_dpe import normalize_code_commune
        from pyspark.sql.types import StructType, StructField, StringType

        schema = StructType([StructField("code_commune", StringType(), True)])
        df = spark.createDataFrame([("75056",), ("1001",), (" 2A004 ",)], schema)
        result = normalize_code_commune(df)
        codes = [r.code_commune for r in result.collect()]
        assert "01001" in codes
        assert all(len(c) == 5 for c in codes)

    def test_filter_consommation_exclut_zero_et_aberrations(self, spark):
        from src.processing.spark_dpe import filter_consommation
        from pyspark.sql.types import StructType, StructField, DoubleType

        schema = StructType([StructField("consommation_moyenne", DoubleType(), True)])
        df = spark.createDataFrame([
            (150.0,),    # OK
            (0.0,),      # nul → exclu
            (-10.0,),    # négatif → exclu
            (5000.0,),   # > CONSO_MAX → exclu
            (None,),     # null → exclu
            (450.0,),    # OK (logement énergivore mais réaliste)
        ], schema)
        result = filter_consommation(df)
        consomations = [r.consommation_moyenne for r in result.collect()]
        assert sorted(consomations) == [150.0, 450.0]

    def test_aggregate_by_commune_compte_par_classe(self, spark):
        from src.processing.spark_dpe import aggregate_by_commune
        from pyspark.sql.types import StructType, StructField, StringType, DoubleType

        schema = StructType([
            StructField("code_commune", StringType(), True),
            StructField("classe_energie", StringType(), True),
            StructField("consommation_moyenne", DoubleType(), True),
        ])
        df = spark.createDataFrame([
            ("75056", "A", 50.0),
            ("75056", "A", 60.0),
            ("75056", "B", 120.0),
            ("75056", "G", 450.0),
            ("13055", "C", 200.0),
        ], schema)
        result = aggregate_by_commune(df)
        rows = {r.code_commune: r for r in result.collect()}

        paris = rows["75056"]
        assert paris.nb_dpe_total == 4
        assert paris.nb_classe_a == 2
        assert paris.nb_classe_b == 1
        assert paris.nb_classe_g == 1
        assert paris.pct_classe_a == pytest.approx(50.0)

        marseille = rows["13055"]
        assert marseille.nb_dpe_total == 1
        assert marseille.nb_classe_c == 1

    def test_aggregate_by_commune_consommation_moyenne(self, spark):
        from src.processing.spark_dpe import aggregate_by_commune
        from pyspark.sql.types import StructType, StructField, StringType, DoubleType

        schema = StructType([
            StructField("code_commune", StringType(), True),
            StructField("classe_energie", StringType(), True),
            StructField("consommation_moyenne", DoubleType(), True),
        ])
        df = spark.createDataFrame([
            ("75056", "B", 100.0),
            ("75056", "D", 300.0),
        ], schema)
        result = aggregate_by_commune(df)
        rows = {r.code_commune: r for r in result.collect()}
        assert rows["75056"].consommation_moyenne_commune == pytest.approx(200.0)
