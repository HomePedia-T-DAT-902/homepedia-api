"""Tests pour src/ingestion/download_dpe.py."""

import gzip
import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.ingestion.download_dpe import (
    _is_sql_dump,
    _parse_sql_value,
    _split_sql_values,
    convert_sql_dump_to_csv,
    decompress_gz,
    download_dpe_ancien,
    download_dpe_nouveau,
    get_datagouv_resource,
)


# ── _parse_sql_value ──────────────────────────────────────────────────────────


def test_parse_sql_value_string():
    assert _parse_sql_value("'hello'") == "hello"


def test_parse_sql_value_null():
    assert _parse_sql_value("NULL") == ""


def test_parse_sql_value_null_lowercase():
    assert _parse_sql_value("null") == ""


def test_parse_sql_value_number():
    assert _parse_sql_value("42") == "42"


def test_parse_sql_value_escaped_quote():
    assert _parse_sql_value("'it\\'s'") == "it's"


def test_parse_sql_value_empty_string():
    assert _parse_sql_value("''") == ""


def test_parse_sql_value_strips_spaces():
    assert _parse_sql_value("  'hello'  ") == "hello"


def test_parse_sql_value_backslash():
    assert _parse_sql_value("'a\\\\b'") == "a\\b"


# ── _split_sql_values ─────────────────────────────────────────────────────────


def test_split_sql_values_simple():
    result = _split_sql_values("1,'foo','bar'")
    assert result == ["1", "'foo'", "'bar'"]


def test_split_sql_values_comma_in_string():
    result = _split_sql_values("1,'foo,bar',3")
    assert result == ["1", "'foo,bar'", "3"]


def test_split_sql_values_null():
    result = _split_sql_values("1,NULL,'baz'")
    assert result == ["1", "NULL", "'baz'"]


def test_split_sql_values_empty_string():
    result = _split_sql_values("1,'',3")
    assert result == ["1", "''", "3"]


def test_split_sql_values_single_value():
    result = _split_sql_values("'only'")
    assert result == ["'only'"]


def test_split_sql_values_escaped_quote_inside():
    result = _split_sql_values("'it\\'s fine',2")
    assert result == ["'it\\'s fine'", "2"]


# ── _is_sql_dump ──────────────────────────────────────────────────────────────


def test_is_sql_dump_true(tmp_path):
    gz_path = tmp_path / "dump.sql.gz"
    content = b"-- MySQL dump 10.13\nCREATE TABLE `dpe` (\n  `id` int(11) NOT NULL\n);\n"
    with gzip.open(gz_path, "wb") as f:
        f.write(content)
    assert _is_sql_dump(gz_path) is True


def test_is_sql_dump_false_csv(tmp_path):
    gz_path = tmp_path / "data.csv.gz"
    content = b"numero_dpe,date_etablissement,classe_energie\n1,2022-01-01,B\n"
    with gzip.open(gz_path, "wb") as f:
        f.write(content)
    assert _is_sql_dump(gz_path) is False


def test_is_sql_dump_with_insert(tmp_path):
    gz_path = tmp_path / "dump.sql.gz"
    content = b"INSERT INTO `dpe` VALUES (1,'2022-01-01','B');\n"
    with gzip.open(gz_path, "wb") as f:
        f.write(content)
    assert _is_sql_dump(gz_path) is True


# ── convert_sql_dump_to_csv ───────────────────────────────────────────────────


def _make_sql_dump(tmp_path: Path, rows: list[tuple]) -> Path:
    """Crée un .sql.gz minimal avec CREATE TABLE + INSERT INTO."""
    gz_path = tmp_path / "dump.sql.gz"
    lines = [
        "-- MySQL dump\n",
        "CREATE TABLE `dpe` (\n",
        "  `numero_dpe` varchar(20),\n",
        "  `date_etablissement` date,\n",
        "  `classe_energie` char(1)\n",
        ");\n",
    ]
    for row in rows:
        vals = ",".join(
            f"'{v}'" if isinstance(v, str) else ("NULL" if v is None else str(v))
            for v in row
        )
        lines.append(f"INSERT INTO `dpe` VALUES ({vals});\n")

    with gzip.open(gz_path, "wt", encoding="utf-8") as f:
        f.writelines(lines)
    return gz_path


def test_convert_sql_dump_produces_csv(tmp_path):
    rows = [("DPE001", "2020-01-15", "B"), ("DPE002", "2019-06-01", "D")]
    gz_path = _make_sql_dump(tmp_path, rows)
    csv_dest = tmp_path / "output.csv"

    convert_sql_dump_to_csv(gz_path, csv_dest)

    assert csv_dest.exists()
    with open(csv_dest, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        result = list(reader)

    assert len(result) == 2
    assert result[0]["numero_dpe"] == "DPE001"
    assert result[0]["classe_energie"] == "B"
    assert result[1]["numero_dpe"] == "DPE002"


def test_convert_sql_dump_handles_null(tmp_path):
    rows = [("DPE001", None, "C")]
    gz_path = _make_sql_dump(tmp_path, rows)
    csv_dest = tmp_path / "output.csv"

    convert_sql_dump_to_csv(gz_path, csv_dest)

    with open(csv_dest, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        result = list(reader)

    assert result[0]["date_etablissement"] == ""


def test_convert_sql_dump_columns_from_create_table(tmp_path):
    rows = [("DPE999", "2021-01-01", "A")]
    gz_path = _make_sql_dump(tmp_path, rows)
    csv_dest = tmp_path / "output.csv"

    convert_sql_dump_to_csv(gz_path, csv_dest)

    with open(csv_dest, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)

    assert header == ["numero_dpe", "date_etablissement", "classe_energie"]


def test_convert_sql_dump_empty(tmp_path):
    """Un dump sans INSERT INTO doit produire un CSV vide (ou juste header)."""
    gz_path = tmp_path / "empty.sql.gz"
    with gzip.open(gz_path, "wt", encoding="utf-8") as f:
        f.write("-- MySQL dump\nCREATE TABLE `dpe` (`id` int);\n")

    csv_dest = tmp_path / "output.csv"
    convert_sql_dump_to_csv(gz_path, csv_dest)
    # Ne doit pas planter — le CSV peut être vide ou absent
    # (aucune ligne = pas d'en-tête non plus, writer jamais initialisé)


# ── get_datagouv_resource ─────────────────────────────────────────────────────


def test_get_datagouv_resource_prefers_format_hint():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "resources": [
            {"title": "Notice", "format": "pdf", "url": "http://ex.com/notice.pdf"},
            {"title": "Données CSV", "format": "csv", "url": "http://ex.com/data.csv"},
        ]
    }

    with patch("src.ingestion.download_dpe.requests.get", return_value=mock_response):
        url, title = get_datagouv_resource("fake-id", ["csv"])

    assert url == "http://ex.com/data.csv"


def test_get_datagouv_resource_fallback_to_first():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "resources": [
            {"title": "Seule ressource", "format": "zip", "url": "http://ex.com/data.zip"},
        ]
    }

    with patch("src.ingestion.download_dpe.requests.get", return_value=mock_response):
        url, title = get_datagouv_resource("fake-id", ["csv"])

    assert url == "http://ex.com/data.zip"


def test_get_datagouv_resource_empty_raises():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"resources": []}

    with patch("src.ingestion.download_dpe.requests.get", return_value=mock_response):
        with pytest.raises(RuntimeError):
            get_datagouv_resource("fake-id", ["csv"])


# ── download_dpe_nouveau ──────────────────────────────────────────────────────


def test_download_dpe_nouveau_skips_existing(tmp_path):
    (tmp_path / "dpe_nouveau.csv").write_text("existing")

    with patch("src.ingestion.download_dpe.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_dpe.get_datagouv_resource") as mock_api:
            download_dpe_nouveau(force=False)
            mock_api.assert_not_called()


def test_download_dpe_nouveau_force_redownloads(tmp_path):
    (tmp_path / "dpe_nouveau.csv").write_text("existing")

    with patch("src.ingestion.download_dpe.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_dpe._download_ademe_paginated") as mock_dl:
            download_dpe_nouveau(force=True)
            mock_dl.assert_called_once()


# ── decompress_gz ─────────────────────────────────────────────────────────────


def test_decompress_gz(tmp_path):
    content = b"numero_dpe,classe_energie\nDPE001,B\n"
    gz_path = tmp_path / "test.csv.gz"
    dest_path = tmp_path / "test.csv"

    with gzip.open(gz_path, "wb") as f:
        f.write(content)

    decompress_gz(gz_path, dest_path)

    assert dest_path.exists()
    assert dest_path.read_bytes() == content
    assert not gz_path.exists()
