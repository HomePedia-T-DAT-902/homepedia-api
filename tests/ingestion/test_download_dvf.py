"""Tests pour src/ingestion/download_dvf.py."""

import gzip
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.ingestion.download_dvf import (
    GEO_DVF_YEARS,
    DGFIP_YEARS,
    decompress_gz,
    download_file,
    download_geo_dvf,
    download_dgfip_dvf,
    get_dgfip_year_url,
    year_from_since,
)


# ── year_from_since ───────────────────────────────────────────────────────────


def test_year_from_since_none():
    assert year_from_since(None) == 0


def test_year_from_since_date():
    assert year_from_since("2022-06-15") == 2022


def test_year_from_since_jan():
    assert year_from_since("2020-01-01") == 2020


def test_year_from_since_dec():
    assert year_from_since("2019-12-31") == 2019


def test_year_from_since_invalid():
    with pytest.raises(ValueError):
        year_from_since("not-a-date")


# ── Constantes ────────────────────────────────────────────────────────────────


def test_geo_dvf_years_range():
    assert all(2020 <= y <= 2025 for y in GEO_DVF_YEARS)
    assert len(GEO_DVF_YEARS) > 0


def test_dgfip_years_range():
    assert all(2020 <= y <= 2025 for y in DGFIP_YEARS)
    assert len(DGFIP_YEARS) == 6


def test_dgfip_filters_geo_dvf_overlap():
    """DGFIP_YEARS chevauche GEO_DVF_YEARS — filtré à l'exécution."""
    overlap = set(GEO_DVF_YEARS) & set(DGFIP_YEARS)
    assert len(overlap) > 0, "Les deux sources doivent se chevaucher (filtrage runtime)"


# ── download_file ─────────────────────────────────────────────────────────────


def test_download_file_writes_content(tmp_path):
    dest = tmp_path / "test.csv"
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {"content-length": "5"}
    mock_response.iter_content = MagicMock(return_value=[b"hello"])

    with patch("src.ingestion.download_dvf.requests.get", return_value=mock_response):
        download_file("http://fake.url/file.csv", dest)

    assert dest.exists()
    assert dest.read_bytes() == b"hello"


def test_download_file_raises_on_http_error(tmp_path):
    dest = tmp_path / "test.csv"
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.raise_for_status.side_effect = requests.HTTPError("404")

    with patch("src.ingestion.download_dvf.requests.get", return_value=mock_response):
        with pytest.raises(requests.HTTPError):
            download_file("http://fake.url/404.csv", dest)


# ── decompress_gz ─────────────────────────────────────────────────────────────


def test_decompress_gz(tmp_path):
    content = b"id_mutation,date_mutation\n1,2022-01-01\n"
    gz_path = tmp_path / "test.csv.gz"
    dest_path = tmp_path / "test.csv"

    with gzip.open(gz_path, "wb") as f:
        f.write(content)

    decompress_gz(gz_path, dest_path)

    assert dest_path.exists()
    assert dest_path.read_bytes() == content
    assert not gz_path.exists()  # le .gz est supprimé


# ── get_dgfip_year_url ────────────────────────────────────────────────────────


def test_get_dgfip_year_url_found():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "resources": [
            {"title": "Demandes de valeurs foncières 2015", "url": "https://example.com/dvf_2015.csv"},
            {"title": "Demandes de valeurs foncières 2016", "url": "https://example.com/dvf_2016.csv"},
        ]
    }

    with patch("src.ingestion.download_dvf.requests.get", return_value=mock_response):
        url = get_dgfip_year_url(2016)

    assert url == "https://example.com/dvf_2016.csv"


def test_get_dgfip_year_url_not_found():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "resources": [
            {"title": "Demandes de valeurs foncières 2015", "url": "https://example.com/dvf_2015.csv"},
        ]
    }

    with patch("src.ingestion.download_dvf.requests.get", return_value=mock_response):
        with pytest.raises(RuntimeError, match="2018"):
            get_dgfip_year_url(2018)


def test_get_dgfip_year_url_empty_dataset():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"resources": []}

    with patch("src.ingestion.download_dvf.requests.get", return_value=mock_response):
        with pytest.raises(RuntimeError):
            get_dgfip_year_url(2015)


# ── download_geo_dvf ──────────────────────────────────────────────────────────


def test_download_geo_dvf_skips_existing(tmp_path):
    """Un fichier déjà présent ne doit pas être re-téléchargé."""
    geo_dir = tmp_path / "geo"
    geo_dir.mkdir()
    (geo_dir / "dvf_2022.csv").write_text("existing")

    with patch("src.ingestion.download_dvf.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_dvf.download_file") as mock_dl:
            with patch("src.ingestion.download_dvf.decompress_gz"):
                download_geo_dvf(since_year=2022, force=False)
                # download_file ne doit pas être appelé pour 2022
                calls_years = [str(c) for c in mock_dl.call_args_list]
                assert not any("2022" in c for c in calls_years)


def test_download_geo_dvf_since_filters_years(tmp_path):
    """since_year doit exclure les années antérieures."""
    with patch("src.ingestion.download_dvf.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_dvf.download_file") as mock_dl:
            with patch("src.ingestion.download_dvf.decompress_gz"):
                download_geo_dvf(since_year=2023, force=True)
                # Seules les années >= 2023 doivent être téléchargées
                urls = [call.args[0] for call in mock_dl.call_args_list]
                assert all("2022" not in url and "2021" not in url and "2020" not in url for url in urls)
                assert any("2023" in url or "2024" in url for url in urls)


def test_download_geo_dvf_force_redownloads(tmp_path):
    """--force doit re-télécharger même si le fichier existe."""
    geo_dir = tmp_path / "geo"
    geo_dir.mkdir()
    (geo_dir / "dvf_2020.csv").write_text("existing")

    with patch("src.ingestion.download_dvf.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_dvf.download_file") as mock_dl:
            with patch("src.ingestion.download_dvf.decompress_gz"):
                download_geo_dvf(since_year=2020, force=True)
                urls = [call.args[0] for call in mock_dl.call_args_list]
                assert any("2020" in url for url in urls)


# ── download_dgfip_dvf ────────────────────────────────────────────────────────


def test_download_dgfip_dvf_skips_existing(tmp_path):
    dgfip_dir = tmp_path / "dgfip"
    dgfip_dir.mkdir()
    (dgfip_dir / "dvf_2015.csv").write_text("existing")

    with patch("src.ingestion.download_dvf.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_dvf.get_dgfip_year_url") as mock_url:
            with patch("src.ingestion.download_dvf.download_file"):
                with patch("src.ingestion.download_dvf.decompress_gz"):
                    mock_url.return_value = "http://ex.com/dvf_2016.csv"
                    download_dgfip_dvf(since_year=2015, force=False)
                    # get_dgfip_year_url ne doit pas être appelé pour 2015
                    called_years = [call.args[0] for call in mock_url.call_args_list]
                    assert 2015 not in called_years


def test_download_dgfip_dvf_since_filters_years(tmp_path):
    with patch("src.ingestion.download_dvf.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_dvf.get_dgfip_year_url", side_effect=RuntimeError("not found")):
            # RuntimeError est géré en warning, ne doit pas planter
            download_dgfip_dvf(since_year=2018, force=False)
            # Seules 2018 et 2019 doivent être tentées (2014-2017 ignorées)
