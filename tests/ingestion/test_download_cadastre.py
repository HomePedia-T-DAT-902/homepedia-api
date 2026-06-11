"""Tests pour src/ingestion/download_cadastre.py."""

import gzip
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from src.ingestion.download_cadastre import (
    CADASTRE_BASE,
    DEPARTEMENTS,
    download_dept,
    download_all,
)


# ── Constantes ────────────────────────────────────────────────────────────────


def test_departements_contient_metropole():
    """Les 95 départements métropolitains + Corse doivent être présents."""
    for dept in ["01", "13", "33", "75", "69", "59", "2A", "2B"]:
        assert dept in DEPARTEMENTS, f"Département {dept} manquant"


def test_departements_contient_dom():
    for dept in ["971", "972", "973", "974", "976"]:
        assert dept in DEPARTEMENTS, f"DOM {dept} manquant"


def test_departements_pas_de_doublons():
    assert len(DEPARTEMENTS) == len(set(DEPARTEMENTS))


def test_departements_pas_de_zero_isole():
    """Le département '0' ne doit pas exister — les codes commencent à '01'."""
    assert "0" not in DEPARTEMENTS
    assert "00" not in DEPARTEMENTS


def test_cadastre_base_url_contient_placeholder():
    assert "{dept}" in CADASTRE_BASE


# ── download_dept ─────────────────────────────────────────────────────────────


def test_download_dept_skips_si_existant(tmp_path):
    """Un fichier déjà présent ne doit pas être re-téléchargé."""
    (tmp_path / "parcelles_75.geojson.gz").write_bytes(b"data")

    with patch("src.ingestion.download_cadastre.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_cadastre.download_file") as mock_dl:
            result = download_dept("75", force=False)

    assert result is False
    mock_dl.assert_not_called()


def test_download_dept_force_redownload(tmp_path):
    """--force doit re-télécharger même si le fichier existe."""
    (tmp_path / "parcelles_75.geojson.gz").write_bytes(b"old data")

    with patch("src.ingestion.download_cadastre.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_cadastre.download_file") as mock_dl:
            result = download_dept("75", force=True)

    assert result is True
    mock_dl.assert_called_once()


def test_download_dept_retourne_true_si_telecharge(tmp_path):
    with patch("src.ingestion.download_cadastre.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_cadastre.download_file"):
            result = download_dept("13", force=False)

    assert result is True


def test_download_dept_http_error_retourne_false(tmp_path):
    with patch("src.ingestion.download_cadastre.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_cadastre.download_file",
                   side_effect=requests.HTTPError("404")):
            result = download_dept("75", force=False)

    assert result is False


def test_download_dept_nettoie_fichier_partiel_sur_erreur(tmp_path):
    """En cas d'erreur, le fichier partiel doit être supprimé."""
    gz_path = tmp_path / "parcelles_75.geojson.gz"

    def fake_download(url, dest, **kwargs):
        dest.write_bytes(b"partial")
        raise requests.HTTPError("500")

    with patch("src.ingestion.download_cadastre.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_cadastre.download_file", side_effect=fake_download):
            download_dept("75", force=False)

    assert not gz_path.exists()


def test_download_dept_url_contient_code_dept(tmp_path):
    """L'URL construite doit contenir le code département."""
    captured_urls = []

    def fake_download(url, dest, **kwargs):
        captured_urls.append(url)

    with patch("src.ingestion.download_cadastre.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_cadastre.download_file", side_effect=fake_download):
            download_dept("2A", force=False)

    assert len(captured_urls) == 1
    assert "2A" in captured_urls[0]


# ── download_all ──────────────────────────────────────────────────────────────


def test_download_all_appelle_chaque_dept(tmp_path):
    with patch("src.ingestion.download_cadastre.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_cadastre.download_dept", return_value=True) as mock_dept:
            download_all(["75", "13", "69"], force=False)

    assert mock_dept.call_count == 3
    called_depts = [c.args[0] for c in mock_dept.call_args_list]
    assert sorted(called_depts) == ["13", "69", "75"]


def test_download_all_continue_apres_erreur(tmp_path):
    """Une erreur HTTP sur un département ne doit pas arrêter les suivants.
    On mock download_file (et non download_dept) pour que download_dept
    gère l'exception en interne et continue sur le département suivant.
    """
    import requests as req
    call_count = [0]

    def fake_download_file(url, dest, **kwargs):
        call_count[0] += 1
        if "13" in url:
            raise req.HTTPError("500 Server Error")

    with patch("src.ingestion.download_cadastre.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_cadastre.download_file", side_effect=fake_download_file):
            # Ne doit pas lever d'exception
            download_all(["75", "13", "69"], force=False)

    assert call_count[0] == 3


def test_download_all_passe_force(tmp_path):
    with patch("src.ingestion.download_cadastre.RAW_DIR", tmp_path):
        with patch("src.ingestion.download_cadastre.download_dept", return_value=True) as mock_dept:
            download_all(["75"], force=True)

    mock_dept.assert_called_once_with("75", force=True)


# ── download_file (intégration) ───────────────────────────────────────────────


def test_download_file_ecrit_bytes_bruts(tmp_path):
    """download_file doit écrire les bytes bruts sans décompresser."""
    from src.ingestion.download_cadastre import download_file

    gz_content = gzip.compress(b'{"type":"FeatureCollection","features":[]}')
    dest = tmp_path / "parcelles_75.geojson.gz"

    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {"content-length": str(len(gz_content))}
    mock_response.raw.decode_content = True
    mock_response.raw.stream = MagicMock(return_value=[gz_content])

    with patch("src.ingestion.download_cadastre.requests.get", return_value=mock_response):
        download_file("http://fake.url/parcelles", dest)

    assert dest.exists()
    # Le fichier doit être lisible comme gzip
    with gzip.open(dest, "rb") as f:
        content = f.read()
    assert b"FeatureCollection" in content


def test_download_file_leve_http_error(tmp_path):
    from src.ingestion.download_cadastre import download_file

    dest = tmp_path / "parcelles_75.geojson.gz"
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.raise_for_status.side_effect = requests.HTTPError("404")

    with patch("src.ingestion.download_cadastre.requests.get", return_value=mock_response):
        with pytest.raises(requests.HTTPError):
            download_file("http://fake.url/404", dest)
