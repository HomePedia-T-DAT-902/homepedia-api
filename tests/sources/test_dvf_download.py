"""Tests pour src/sources/dvf/download.py."""

import gzip
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.sources.dvf.config import DGFIP_YEARS, GEO_DVF_YEARS
from src.sources.dvf.download import (
    _get_dgfip_year_url,
    download_dgfip_dvf,
    download_geo_dvf,
)
from src.sources.utils import decompress_gz, download_file


# ── Constantes ────────────────────────────────────────────────────────────────


def test_geo_dvf_years_range():
    assert all(2020 <= y <= 2025 for y in GEO_DVF_YEARS)
    assert len(GEO_DVF_YEARS) > 0


def test_dgfip_years_range():
    assert all(2020 <= y <= 2025 for y in DGFIP_YEARS)
    assert len(DGFIP_YEARS) == 6


def test_dgfip_filters_geo_dvf_overlap():
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

    with patch("src.sources.utils.requests.get", return_value=mock_response):
        download_file("http://fake.url/file.csv", dest)

    assert dest.exists()
    assert dest.read_bytes() == b"hello"


def test_download_file_raises_on_http_error(tmp_path):
    dest = tmp_path / "test.csv"
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.raise_for_status.side_effect = requests.HTTPError("404")

    with patch("src.sources.utils.requests.get", return_value=mock_response):
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
    assert not gz_path.exists()


# ── _get_dgfip_year_url ───────────────────────────────────────────────────────


def test_get_dgfip_year_url_found():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "resources": [
            {"title": "Demandes de valeurs foncières 2015", "format": "txt", "url": "https://example.com/dvf_2015.txt"},
            {"title": "Demandes de valeurs foncières 2016", "format": "txt", "url": "https://example.com/dvf_2016.txt"},
        ]
    }

    with patch("src.sources.dvf.download.requests.get", return_value=mock_response):
        url = _get_dgfip_year_url(2016)

    assert url == "https://example.com/dvf_2016.txt"


def test_get_dgfip_year_url_not_found():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "resources": [
            {"title": "Demandes de valeurs foncières 2015", "format": "txt", "url": "https://example.com/dvf_2015.txt"},
        ]
    }

    with patch("src.sources.dvf.download.requests.get", return_value=mock_response):
        with pytest.raises(RuntimeError, match="2018"):
            _get_dgfip_year_url(2018)


def test_get_dgfip_year_url_empty_dataset():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"resources": []}

    with patch("src.sources.dvf.download.requests.get", return_value=mock_response):
        with pytest.raises(RuntimeError):
            _get_dgfip_year_url(2015)


# ── download_geo_dvf ──────────────────────────────────────────────────────────


def test_download_geo_dvf_skips_existing(tmp_path):
    geo_dir = tmp_path / "geo"
    geo_dir.mkdir()
    (geo_dir / "dvf_2022.csv").write_text("existing")

    with patch("src.sources.dvf.download.download_file") as mock_dl:
        with patch("src.sources.dvf.download.decompress_gz"):
            download_geo_dvf(raw_dir=tmp_path, since_year=2022, force=False)
            calls_years = [str(c) for c in mock_dl.call_args_list]
            assert not any("2022" in c for c in calls_years)


def test_download_geo_dvf_since_filters_years(tmp_path):
    with patch("src.sources.dvf.download.download_file") as mock_dl:
        with patch("src.sources.dvf.download.decompress_gz"):
            download_geo_dvf(raw_dir=tmp_path, since_year=2023, force=True)
            urls = [call.args[0] for call in mock_dl.call_args_list]
            assert all("2022" not in url and "2021" not in url and "2020" not in url for url in urls)
            assert any("2023" in url or "2024" in url for url in urls)


def test_download_geo_dvf_force_redownloads(tmp_path):
    geo_dir = tmp_path / "geo"
    geo_dir.mkdir()
    (geo_dir / "dvf_2020.csv").write_text("existing")

    with patch("src.sources.dvf.download.download_file") as mock_dl:
        with patch("src.sources.dvf.download.decompress_gz"):
            download_geo_dvf(raw_dir=tmp_path, since_year=2020, force=True)
            urls = [call.args[0] for call in mock_dl.call_args_list]
            assert any("2020" in url for url in urls)


# ── download_dgfip_dvf ────────────────────────────────────────────────────────


def test_download_dgfip_dvf_skips_existing(tmp_path):
    dgfip_dir = tmp_path / "dgfip"
    dgfip_dir.mkdir()
    (dgfip_dir / "dvf_2025.csv").write_text("existing")

    with patch("src.sources.dvf.download._get_dgfip_year_url") as mock_url:
        download_dgfip_dvf(raw_dir=tmp_path, since_year=2025, force=False)
        called_years = [call.args[0] for call in mock_url.call_args_list]
        assert 2025 not in called_years


def test_download_dgfip_dvf_url_not_found_warns(tmp_path):
    with patch("src.sources.dvf.download._get_dgfip_year_url", side_effect=RuntimeError("not found")):
        download_dgfip_dvf(raw_dir=tmp_path, since_year=2025, force=False)
