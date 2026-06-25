"""Tests pour src/sources/dpe/download.py."""

from unittest.mock import patch

from src.sources.dpe.download import download_dpe_ancien, download_dpe_nouveau


# ── download_dpe_nouveau ──────────────────────────────────────────────────────


def test_download_dpe_nouveau_skips_existing(tmp_path):
    (tmp_path / "dpe_nouveau.csv").write_text("existing")

    with patch("src.sources.dpe.download._download_ademe_paginated") as mock_dl:
        download_dpe_nouveau(raw_dir=tmp_path, force=False)
        mock_dl.assert_not_called()


def test_download_dpe_nouveau_force_redownloads(tmp_path):
    (tmp_path / "dpe_nouveau.csv").write_text("existing")

    with patch("src.sources.dpe.download._download_ademe_paginated") as mock_dl:
        download_dpe_nouveau(raw_dir=tmp_path, force=True)
        mock_dl.assert_called_once()


# ── download_dpe_ancien ───────────────────────────────────────────────────────


def test_download_dpe_ancien_skips_existing(tmp_path):
    (tmp_path / "dpe_ancien.csv").write_text("existing")

    with patch("src.sources.dpe.download._download_ademe_paginated") as mock_dl:
        download_dpe_ancien(raw_dir=tmp_path, force=False)
        mock_dl.assert_not_called()


def test_download_dpe_ancien_force_redownloads(tmp_path):
    (tmp_path / "dpe_ancien.csv").write_text("existing")

    with patch("src.sources.dpe.download._download_ademe_paginated") as mock_dl:
        download_dpe_ancien(raw_dir=tmp_path, force=True)
        mock_dl.assert_called_once()
