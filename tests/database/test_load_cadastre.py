"""Tests pour src/database/load_cadastre.py."""

import gzip
import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.database.load_cadastre import (
    BATCH_SIZE,
    _build_csv_buffer,
    _flush_batch,
    _v,
    iter_features,
    load_dept,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

FEATURE_1 = {
    "type": "Feature",
    "properties": {
        "id": "75056000AB0001",
        "commune": "75056",
        "prefixe": "000",
        "section": "AB",
        "numero": "0001",
        "contenance": 120,
        "created": "2020-01-01",
        "updated": "2023-06-15",
    },
    "geometry": {"type": "Polygon", "coordinates": [[[2.3, 48.8], [2.31, 48.8], [2.31, 48.81], [2.3, 48.8]]]},
}

FEATURE_NO_GEOM = {
    "type": "Feature",
    "properties": {"id": "75056000AB0002", "commune": "75056"},
    "geometry": None,
}

FEATURE_NULLS = {
    "type": "Feature",
    "properties": {
        "id": "13055000AA0001",
        "commune": "13055",
        "prefixe": None,
        "section": "AA",
        "numero": "0001",
        "contenance": None,
        "created": None,
        "updated": None,
    },
    "geometry": {"type": "Polygon", "coordinates": [[[5.3, 43.2], [5.31, 43.2], [5.31, 43.21], [5.3, 43.2]]]},
}


def make_gz(tmp_path: Path, features: list, filename: str = "parcelles_75.geojson.gz") -> Path:
    """Crée un fichier GeoJSON.gz minimal avec les features données."""
    geojson = json.dumps({"type": "FeatureCollection", "features": features})
    gz_path = tmp_path / filename
    with gzip.open(gz_path, "wt", encoding="utf-8") as f:
        f.write(geojson)
    return gz_path


# ── _v ────────────────────────────────────────────────────────────────────────


def test_v_none_retourne_null():
    assert _v(None) == "\\N"


def test_v_chaine_vide_retourne_null():
    assert _v("") == "\\N"


def test_v_valeur_normale():
    assert _v("75056") == "75056"
    assert _v(120) == "120"


# ── _build_csv_buffer ─────────────────────────────────────────────────────────


def test_build_csv_buffer_une_feature():
    buf = _build_csv_buffer([FEATURE_1])
    content = buf.read()
    assert "75056000AB0001" in content
    assert "75056" in content
    assert "Polygon" in content


def test_build_csv_buffer_ignore_feature_sans_geom():
    buf = _build_csv_buffer([FEATURE_NO_GEOM])
    content = buf.read()
    assert content.strip() == ""


def test_build_csv_buffer_nulls_encodés():
    buf = _build_csv_buffer([FEATURE_NULLS])
    content = buf.read()
    assert "\\N" in content   # contenance et dates sont null


def test_build_csv_buffer_plusieurs_features():
    buf = _build_csv_buffer([FEATURE_1, FEATURE_NULLS])
    lines = [l for l in buf.read().splitlines() if l.strip()]
    assert len(lines) == 2


# ── iter_features ─────────────────────────────────────────────────────────────


def test_iter_features_lit_toutes_les_features(tmp_path):
    gz_path = make_gz(tmp_path, [FEATURE_1, FEATURE_NULLS])
    features = list(iter_features(gz_path))
    assert len(features) == 2
    ids = {f["properties"]["id"] for f in features}
    assert "75056000AB0001" in ids
    assert "13055000AA0001" in ids


def test_iter_features_fichier_vide(tmp_path):
    gz_path = make_gz(tmp_path, [])
    features = list(iter_features(gz_path))
    assert features == []


def test_iter_features_fallback_sans_ijson(tmp_path):
    """Même sans ijson, les features doivent être lues correctement."""
    gz_path = make_gz(tmp_path, [FEATURE_1])
    with patch.dict("sys.modules", {"ijson": None}):
        import importlib
        import src.database.load_cadastre as mod
        # Forcer le rechargement pour capturer le fallback
        features = list(mod.iter_features(gz_path))
    assert len(features) == 1


# ── load_dept ─────────────────────────────────────────────────────────────────


def _make_mock_conn():
    """Crée un mock de connexion psycopg2."""
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cur


def test_load_dept_retourne_nb_parcelles(tmp_path):
    """load_dept doit retourner le nombre total de parcelles traitées."""
    gz_path = make_gz(tmp_path, [FEATURE_1, FEATURE_NULLS])
    conn, cur = _make_mock_conn()

    result = load_dept(conn, gz_path)

    assert result == 2  # 2 features avec géométrie


def test_load_dept_ignore_feature_sans_geom(tmp_path):
    """Les features sans géométrie ne comptent pas."""
    gz_path = make_gz(tmp_path, [FEATURE_1, FEATURE_NO_GEOM])
    conn, cur = _make_mock_conn()

    result = load_dept(conn, gz_path)

    assert result == 1


def test_load_dept_commit_apres_chaque_batch(tmp_path):
    """Un commit doit être appelé après chaque batch."""
    # Créer 3 features — avec BATCH_SIZE mocké à 2, on attend 2 commits + 1 commit final
    gz_path = make_gz(tmp_path, [FEATURE_1, FEATURE_NULLS, FEATURE_1])
    conn, cur = _make_mock_conn()

    with patch("src.database.load_cadastre.BATCH_SIZE", 2):
        load_dept(conn, gz_path)

    # 2 batches → au moins 2 commits (+ le commit de CREATE TEMP TABLE)
    assert conn.commit.call_count >= 2


def test_load_dept_cree_table_temporaire(tmp_path):
    """La table temporaire doit être créée avant le chargement."""
    gz_path = make_gz(tmp_path, [FEATURE_1])
    conn, cur = _make_mock_conn()

    load_dept(conn, gz_path)

    # Vérifie qu'un CREATE TEMP TABLE a été exécuté
    execute_calls = [str(c) for c in cur.execute.call_args_list]
    assert any("tmp_cadastre" in c for c in execute_calls)


def test_load_dept_upsert_sur_conflit(tmp_path):
    """Le SQL d'insertion doit contenir ON CONFLICT DO UPDATE."""
    gz_path = make_gz(tmp_path, [FEATURE_1])
    conn, cur = _make_mock_conn()

    load_dept(conn, gz_path)

    execute_calls = [str(c) for c in cur.execute.call_args_list]
    assert any("ON CONFLICT" in c for c in execute_calls)
