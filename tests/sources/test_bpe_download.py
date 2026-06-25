"""Tests pour src/sources/bpe/download.py."""

import gzip
from unittest.mock import MagicMock, patch

from src.sources.bpe.download import get_resource_url, run as download_bpe
from src.sources.utils import decompress_gz, download_file


# ── get_resource_url ──────────────────────────────────────────────────────────


def test_get_resource_url_prefers_parquet():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "resources": [
            {"title": "BPE CSV", "format": "csv", "url": "http://ex.com/bpe.csv"},
            {"title": "BPE Parquet", "format": "parquet", "url": "http://ex.com/bpe.parquet"},
        ]
    }

    with patch("src.sources.bpe.download.requests.get", return_value=mock_response):
        url, _ = get_resource_url()

    assert url == "http://ex.com/bpe.parquet"


def test_get_resource_url_fallback_csv():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "resources": [
            {"title": "Données BPE24", "format": "csv", "url": "http://ex.com/BPE24.csv"},
        ]
    }

    with patch("src.sources.bpe.download.requests.get", return_value=mock_response):
        url, _ = get_resource_url()

    assert url == "http://ex.com/BPE24.csv"


def test_get_resource_url_unknown_format_falls_back_to_first():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "resources": [
            {"title": "Notice PDF", "format": "pdf", "url": "http://ex.com/notice.pdf"},
        ]
    }

    with patch("src.sources.bpe.download.requests.get", return_value=mock_response):
        url, _ = get_resource_url()

    assert url == "http://ex.com/notice.pdf"


# ── download_bpe (run) ────────────────────────────────────────────────────────


def test_download_bpe_skips_existing(tmp_path):
    (tmp_path / "bpe.csv").write_text("AN;DEPCOM;TYPEQU\n2024;75056;A101\n")

    with patch("src.sources.bpe.download.get_resource_url") as mock_api:
        download_bpe(raw_dir=tmp_path, force=False)
        mock_api.assert_not_called()


def test_download_bpe_force_redownloads(tmp_path):
    (tmp_path / "bpe.csv").write_text("AN;DEPCOM;TYPEQU\n2024;75056;A101\n")

    with patch("src.sources.bpe.download.get_resource_url", return_value=("http://ex.com/bpe.csv", "BPE")):
        with patch("src.sources.bpe.download.download_file") as mock_dl:
            download_bpe(raw_dir=tmp_path, force=True)
            mock_dl.assert_called_once()


def test_download_bpe_decompresses_gz(tmp_path):
    with patch("src.sources.bpe.download.get_resource_url", return_value=("http://ex.com/bpe.csv.gz", "BPE")):
        with patch("src.sources.bpe.download.download_file"):
            with patch("src.sources.bpe.download.decompress_gz") as mock_decomp:
                download_bpe(raw_dir=tmp_path, force=True)
                mock_decomp.assert_called_once()


# ── download_file ─────────────────────────────────────────────────────────────


def test_download_file_writes_content(tmp_path):
    dest = tmp_path / "bpe.csv"
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {"content-length": "27"}
    mock_response.iter_content = MagicMock(return_value=[b"AN;DEPCOM;TYPEQU\n2024;75056"])

    with patch("src.sources.utils.requests.get", return_value=mock_response):
        download_file("http://ex.com/bpe.csv", dest)

    assert dest.exists()
    assert dest.read_bytes() == b"AN;DEPCOM;TYPEQU\n2024;75056"


# ── decompress_gz ─────────────────────────────────────────────────────────────


def test_decompress_gz(tmp_path):
    content = b"AN;DEPCOM;TYPEQU\n2024;75056;A101\n"
    gz_path = tmp_path / "bpe.csv.gz"
    dest_path = tmp_path / "bpe.csv"

    with gzip.open(gz_path, "wb") as f:
        f.write(content)

    decompress_gz(gz_path, dest_path)

    assert dest_path.exists()
    assert dest_path.read_bytes() == content
    assert not gz_path.exists()
