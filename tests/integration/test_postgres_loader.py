"""
Test d'intégration — injection des données dans PostgreSQL.

Prérequis : docker-compose up -d db
    (PostgreSQL + PostGIS sur localhost:5432)

Ce test :
  1. Crée des fixtures minimales (Parquet + GeoJSON) qui imitent les sorties
     de spark_geo.py, spark_dvf.py et spark_dpe.py
  2. Exécute le schéma SQL complet (CREATE TABLE IF NOT EXISTS)
  3. Lance les fonctions de chargement du postgres_loader
  4. Vérifie que les données sont bien en base avec les types attendus

Lancer uniquement ce test :
    pytest tests/integration/test_postgres_loader.py -v -s

Variables d'environnement (optionnelles, valeurs par défaut du docker-compose) :
    POSTGRES_HOST=localhost
    POSTGRES_PORT=5432
    POSTGRES_DB=homepedia
    POSTGRES_USER=homepedia
    POSTGRES_PASSWORD=homepedia_secret
"""

import datetime
import json
import os

import numpy as np
import pandas as pd
import pytest

# ── Skip automatique si la DB est inaccessible ────────────────────────────────

def _db_available() -> bool:
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ.get("POSTGRES_DB", "homepedia"),
            user=os.environ.get("POSTGRES_USER", "homepedia"),
            password=os.environ.get("POSTGRES_PASSWORD", "homepedia_secret"),
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_available(),
    reason="PostgreSQL inaccessible — lancer docker-compose up -d db",
)


# ── Fixtures : données minimales ──────────────────────────────────────────────

# Une région, un département, deux communes — suffisant pour tester toutes les FK

REGION = {"code_region": "11", "nom": "Île-de-France"}
DEPARTEMENT = {"code_departement": "75", "nom": "Paris", "code_region": "11"}
COMMUNES = [
    {
        "code_commune": "75056",
        "nom": "Paris",
        "code_departement": "75",
        "code_region": "11",
        "code_postal": "75001",
        "population": 2_145_906,
        "superficie": 105.4,
        "densite": 20_755.0,
        "latitude": 48.8566,
        "longitude": 2.3522,
    },
    {
        "code_commune": "75101",
        "nom": "Paris 1er Arrondissement",
        "code_departement": "75",
        "code_region": "11",
        "code_postal": "75001",
        "population": 16_266,
        "superficie": 1.83,
        "densite": 8_889.0,
        "latitude": 48.8606,
        "longitude": 2.3477,
    },
]

# GeoJSON minimal (rectangle autour de Paris) pour tester ST_GeomFromGeoJSON
_PARIS_GEOM = {
    "type": "MultiPolygon",
    "coordinates": [[[[2.22, 48.81], [2.47, 48.81], [2.47, 48.90], [2.22, 48.90], [2.22, 48.81]]]],
}

DVF_ROWS = [
    {
        "id_mutation": "MUT001",
        "date_mutation": "2022-06-15",
        "nature_mutation": "Vente",
        "valeur_fonciere": 450_000.0,
        "code_commune": "75056",
        "type_local": "Appartement",
        "surface_reelle_bati": 60.0,
        "nb_pieces": 3,
        "surface_terrain": None,
        "prix_m2": 7_500.0,
        "longitude": 2.3522,
        "latitude": 48.8566,
        "annee": 2022,
        "source": "geo",
    },
    {
        "id_mutation": "MUT002",
        "date_mutation": "2021-03-01",
        "nature_mutation": "Vente",
        "valeur_fonciere": 620_000.0,
        "code_commune": "75056",
        "type_local": "Maison",
        "surface_reelle_bati": 120.0,
        "nb_pieces": 5,
        "surface_terrain": 200.0,
        "prix_m2": 5_166.67,
        "longitude": None,
        "latitude": None,
        "annee": 2021,
        "source": "dgfip",
    },
    {
        "id_mutation": None,
        "date_mutation": "2023-11-20",
        "nature_mutation": "Vente",
        "valeur_fonciere": 280_000.0,
        "code_commune": "75101",
        "type_local": "Appartement",
        "surface_reelle_bati": 35.0,
        "nb_pieces": 1,
        "surface_terrain": None,
        "prix_m2": 8_000.0,
        "longitude": 2.3477,
        "latitude": 48.8606,
        "annee": 2023,
        "source": "geo",
    },
]

DPE_ROWS = [
    {"code_commune": "75056", "date_diagnostic": "2022-01-10", "classe_energie": "B", "consommation_moyenne": 95.0, "source": "nouveau"},
    {"code_commune": "75056", "date_diagnostic": "2021-05-20", "classe_energie": "D", "consommation_moyenne": 230.0, "source": "ancien"},
    {"code_commune": "75056", "date_diagnostic": "2023-03-15", "classe_energie": "A", "consommation_moyenne": 45.0, "source": "nouveau"},
    {"code_commune": "75101", "date_diagnostic": "2022-09-01", "classe_energie": "E", "consommation_moyenne": 320.0, "source": "nouveau"},
]


# ── Helpers pour créer les fixtures ──────────────────────────────────────────


def _make_geo_parquet(tmp_path):
    """Crée les Parquet géo (communes, departements, regions) dans tmp_path/geo/."""
    geo_dir = tmp_path / "processed" / "geo"

    for name, data in [
        ("regions", [REGION]),
        ("departements", [DEPARTEMENT]),
        ("communes", COMMUNES),
    ]:
        d = geo_dir / name
        d.mkdir(parents=True)
        pd.DataFrame(data).to_parquet(d / "part-0.parquet", index=False)

    return geo_dir


def _make_geojson(tmp_path):
    """Crée des GeoJSON minimaux (une feature par entité) dans tmp_path/raw/geo/."""
    raw_dir = tmp_path / "raw" / "geo"
    raw_dir.mkdir(parents=True)

    for filename, code_key, code_value, nom in [
        ("regions-5m.geojson", "code", "11", "Île-de-France"),
        ("departements-5m.geojson", "code", "75", "Paris"),
        ("communes-5m.geojson", "code", "75056", "Paris"),
        ("communes-50m.geojson", "code", "75056", "Paris"),
    ]:
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {code_key: code_value, "nom": nom},
                    "geometry": _PARIS_GEOM,
                }
            ],
        }
        (raw_dir / filename).write_text(json.dumps(geojson), encoding="utf-8")

    return raw_dir


def _make_dvf_parquet(tmp_path):
    """Crée le Parquet DVF dans tmp_path/processed/dvf/."""
    dvf_dir = tmp_path / "processed" / "dvf"
    dvf_dir.mkdir(parents=True)
    df = pd.DataFrame(DVF_ROWS)
    df["date_mutation"] = pd.to_datetime(df["date_mutation"])
    df.to_parquet(dvf_dir / "part-0.parquet", index=False)
    return dvf_dir


def _make_dpe_parquet(tmp_path):
    """Crée le Parquet DPE dans tmp_path/processed/dpe/diagnostics/."""
    dpe_dir = tmp_path / "processed" / "dpe" / "diagnostics"
    dpe_dir.mkdir(parents=True)
    df = pd.DataFrame(DPE_ROWS)
    df["date_diagnostic"] = pd.to_datetime(df["date_diagnostic"])
    df.to_parquet(dpe_dir / "part-0.parquet", index=False)
    return dpe_dir


# ── Fixture pytest : connexion DB + rollback automatique ─────────────────────


@pytest.fixture()
def db_conn():
    """
    Connexion PostgreSQL avec rollback automatique après chaque test.
    Chaque test repart d'une base propre sans avoir à la recréer.
    """
    import psycopg2
    from src.database.postgres_loader import get_connection, init_schema

    conn = get_connection()
    # Démarrer une transaction globale — tout sera rollbacké à la fin
    conn.autocommit = False

    # Initialiser le schéma dans cette transaction
    init_schema(conn)

    yield conn

    # Rollback complet : la base repart comme avant
    conn.rollback()
    conn.close()


# ── Tests ─────────────────────────────────────────────────────────────────────


@requires_db
def test_init_schema_cree_les_tables(db_conn):
    """Le schéma SQL doit créer toutes les tables attendues."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = {row[0] for row in cur.fetchall()}

    expected = {"communes", "departements", "regions", "dvf_transactions", "dpe_diagnostics", "price_trends"}
    assert expected.issubset(tables), f"Tables manquantes : {expected - tables}"


@requires_db
def test_init_schema_cree_extensions_postgis(db_conn):
    """PostGIS et pg_trgm doivent être activées."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension WHERE extname IN ('postgis', 'pg_trgm')")
        extensions = {row[0] for row in cur.fetchall()}
    assert "postgis" in extensions, "Extension PostGIS manquante"


@requires_db
def test_load_geo_regions(tmp_path, db_conn):
    """Les régions doivent être chargées avec géométrie PostGIS."""
    from src.database.postgres_loader import load_regions

    geo_dir = _make_geo_parquet(tmp_path)
    raw_dir = _make_geojson(tmp_path)

    load_regions(db_conn, geo_dir, raw_dir)

    with db_conn.cursor() as cur:
        cur.execute("SELECT code_region, nom, ST_AsText(geom) FROM regions")
        rows = cur.fetchall()

    assert len(rows) == 1
    code, nom, geom_wkt = rows[0]
    assert code == "11"
    assert nom == "Île-de-France"
    assert geom_wkt is not None  # géométrie PostGIS bien insérée


@requires_db
def test_load_geo_departements(tmp_path, db_conn):
    """Les départements doivent respecter la FK vers regions."""
    from src.database.postgres_loader import load_regions, load_departements

    geo_dir = _make_geo_parquet(tmp_path)
    raw_dir = _make_geojson(tmp_path)

    load_regions(db_conn, geo_dir, raw_dir)
    load_departements(db_conn, geo_dir, raw_dir)

    with db_conn.cursor() as cur:
        cur.execute("SELECT code_departement, nom, code_region FROM departements")
        rows = cur.fetchall()

    assert len(rows) == 1
    code, nom, code_region = rows[0]
    assert code == "75"
    assert code_region == "11"


@requires_db
def test_load_geo_communes(tmp_path, db_conn):
    """Les communes doivent avoir geom et geom_simplified (polygones PostGIS)."""
    from src.database.postgres_loader import load_regions, load_departements, load_communes

    geo_dir = _make_geo_parquet(tmp_path)
    raw_dir = _make_geojson(tmp_path)

    load_regions(db_conn, geo_dir, raw_dir)
    load_departements(db_conn, geo_dir, raw_dir)
    load_communes(db_conn, geo_dir, raw_dir)

    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT code_commune, nom, population,
                   ST_AsText(geom) IS NOT NULL AS a_geom,
                   longitude, latitude
            FROM communes
        """)
        rows = {r[0]: r for r in cur.fetchall()}

    # Seul Paris 75056 a une géométrie dans nos GeoJSON de test
    assert "75056" in rows
    code, nom, pop, a_geom, lon, lat = rows["75056"]
    assert nom == "Paris"
    assert pop == 2_145_906
    assert a_geom is True
    assert abs(lon - 2.3522) < 0.001
    assert abs(lat - 48.8566) < 0.001


@requires_db
def test_load_dvf_transactions(tmp_path, db_conn):
    """Les transactions DVF doivent être en base avec prix_m2 et geom pour les géolocalisées."""
    from src.database.postgres_loader import (
        load_regions, load_departements, load_communes, load_dvf_transactions,
    )

    geo_dir = _make_geo_parquet(tmp_path)
    raw_dir = _make_geojson(tmp_path)
    processed_dir = tmp_path / "processed"
    _make_dvf_parquet(tmp_path)

    load_regions(db_conn, geo_dir, raw_dir)
    load_departements(db_conn, geo_dir, raw_dir)
    load_communes(db_conn, geo_dir, raw_dir)
    load_dvf_transactions(db_conn, processed_dir)

    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT id_mutation, code_commune, type_local, prix_m2,
                   ST_AsText(geom) AS geom_wkt
            FROM dvf_transactions
            ORDER BY id_mutation NULLS LAST
        """)
        rows = cur.fetchall()

    assert len(rows) == 3

    # Transaction géolocalisée → doit avoir une géométrie Point
    geo_row = next(r for r in rows if r[0] == "MUT001")
    assert geo_row[2] == "Appartement"
    assert abs(geo_row[3] - 7500.0) < 1
    assert geo_row[4] is not None  # POINT(...) construit depuis lon/lat

    # Transaction sans coordonnées → geom NULL
    dgfip_row = next(r for r in rows if r[0] == "MUT002")
    assert dgfip_row[4] is None


@requires_db
def test_load_dpe_diagnostics(tmp_path, db_conn):
    """Les diagnostics DPE doivent être en base avec classes A-G valides."""
    from src.database.postgres_loader import (
        load_regions, load_departements, load_communes, load_dpe_diagnostics,
    )

    geo_dir = _make_geo_parquet(tmp_path)
    raw_dir = _make_geojson(tmp_path)
    processed_dir = tmp_path / "processed"
    _make_dpe_parquet(tmp_path)

    load_regions(db_conn, geo_dir, raw_dir)
    load_departements(db_conn, geo_dir, raw_dir)
    load_communes(db_conn, geo_dir, raw_dir)
    load_dpe_diagnostics(db_conn, processed_dir)

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM dpe_diagnostics")
        total = cur.fetchone()[0]

        cur.execute("SELECT DISTINCT classe_energie FROM dpe_diagnostics ORDER BY classe_energie")
        classes = [r[0] for r in cur.fetchall()]

        cur.execute("SELECT AVG(consommation_moyenne) FROM dpe_diagnostics WHERE code_commune = '75056'")
        avg_conso = cur.fetchone()[0]

    assert total == 4
    assert set(classes).issubset({"A", "B", "C", "D", "E", "F", "G"})
    assert avg_conso is not None
    assert avg_conso > 0


@requires_db
def test_compute_price_trends(tmp_path, db_conn):
    """price_trends doit avoir une ligne par (commune, annee, trimestre, type_local)."""
    from src.database.postgres_loader import (
        load_regions, load_departements, load_communes,
        load_dvf_transactions, compute_and_load_price_trends,
    )

    geo_dir = _make_geo_parquet(tmp_path)
    raw_dir = _make_geojson(tmp_path)
    processed_dir = tmp_path / "processed"
    _make_dvf_parquet(tmp_path)

    load_regions(db_conn, geo_dir, raw_dir)
    load_departements(db_conn, geo_dir, raw_dir)
    load_communes(db_conn, geo_dir, raw_dir)
    load_dvf_transactions(db_conn, processed_dir)
    compute_and_load_price_trends(db_conn, processed_dir)

    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT code_commune, annee, trimestre, type_local, prix_median_m2, nb_transactions
            FROM price_trends
            ORDER BY code_commune, annee, trimestre
        """)
        rows = cur.fetchall()

    assert len(rows) > 0

    # Vérifier la cohérence : nb_transactions >= 1, prix_median_m2 > 0
    for row in rows:
        code_commune, annee, trimestre, type_local, prix, nb = row
        assert nb >= 1
        assert prix > 0
        assert trimestre in (1, 2, 3, 4)
        assert annee >= 2014


@requires_db
def test_upsert_price_trends_idempotent(tmp_path, db_conn):
    """Lancer compute_and_load_price_trends deux fois ne doit pas dupliquer les lignes."""
    from src.database.postgres_loader import (
        load_regions, load_departements, load_communes,
        load_dvf_transactions, compute_and_load_price_trends,
    )

    geo_dir = _make_geo_parquet(tmp_path)
    raw_dir = _make_geojson(tmp_path)
    processed_dir = tmp_path / "processed"
    _make_dvf_parquet(tmp_path)

    load_regions(db_conn, geo_dir, raw_dir)
    load_departements(db_conn, geo_dir, raw_dir)
    load_communes(db_conn, geo_dir, raw_dir)
    load_dvf_transactions(db_conn, processed_dir)

    compute_and_load_price_trends(db_conn, processed_dir)
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM price_trends")
        count_1 = cur.fetchone()[0]

    compute_and_load_price_trends(db_conn, processed_dir)
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM price_trends")
        count_2 = cur.fetchone()[0]

    assert count_1 == count_2, f"Duplication détectée : {count_1} → {count_2} après 2ème run"


@requires_db
def test_pipeline_complet(tmp_path, db_conn):
    """Test de bout en bout : toutes les étapes enchaînées."""
    from src.database.postgres_loader import (
        load_regions, load_departements, load_communes,
        load_dvf_transactions, load_dpe_diagnostics,
        compute_and_load_price_trends,
    )

    geo_dir = _make_geo_parquet(tmp_path)
    raw_dir = _make_geojson(tmp_path)
    processed_dir = tmp_path / "processed"
    _make_dvf_parquet(tmp_path)
    _make_dpe_parquet(tmp_path)

    load_regions(db_conn, geo_dir, raw_dir)
    load_departements(db_conn, geo_dir, raw_dir)
    load_communes(db_conn, geo_dir, raw_dir)
    load_dvf_transactions(db_conn, processed_dir)
    load_dpe_diagnostics(db_conn, processed_dir)
    compute_and_load_price_trends(db_conn, processed_dir)

    with db_conn.cursor() as cur:
        for table, expected_min in [
            ("regions", 1),
            ("departements", 1),
            ("communes", 1),
            ("dvf_transactions", 3),
            ("dpe_diagnostics", 4),
            ("price_trends", 1),
        ]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            assert count >= expected_min, f"{table} : attendu >= {expected_min}, obtenu {count}"

    # Vérifier que la carte peut récupérer les communes avec géométrie
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT c.code_commune, c.nom, ST_AsGeoJSON(c.geom_simplified) AS geojson
            FROM communes c
            WHERE c.geom_simplified IS NOT NULL
        """)
        communes_avec_geom = cur.fetchall()

    assert len(communes_avec_geom) >= 1
    geojson = json.loads(communes_avec_geom[0][2])
    assert geojson["type"] in ("MultiPolygon", "Polygon")
