"""
Mock de pyspark au niveau sys.modules avant tout import des modules spark_*.
Sans ça, l'import de spark_dvf.py / spark_dpe.py plante si pyspark n'est pas installé.

Exporte PYSPARK_AVAILABLE pour que les fichiers de test sachent si pyspark est réel.
"""

import sys
from unittest.mock import MagicMock

# Détection AVANT tout mock
try:
    import pyspark.sql  # noqa: F401
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    # Injecter des mocks pour que les imports de spark_dvf / spark_dpe ne plantent pas
    pyspark_mock = MagicMock()
    for type_name in [
        "StringType", "DoubleType", "IntegerType", "LongType",
        "DateType", "StructField", "StructType",
    ]:
        getattr(pyspark_mock.sql.types, type_name).return_value = MagicMock()

    sys.modules["pyspark"] = pyspark_mock
    sys.modules["pyspark.sql"] = pyspark_mock.sql
    sys.modules["pyspark.sql.types"] = pyspark_mock.sql.types
    sys.modules["pyspark.sql.functions"] = pyspark_mock.sql.functions
    sys.modules["pyspark.sql.window"] = pyspark_mock.sql.window
