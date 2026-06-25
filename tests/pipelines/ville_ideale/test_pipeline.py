"""Offline tests for the ville-ideale pipeline stages (preprocess, process, load).

These exercise only the pure transforms (no scraping, no database) and use stdlib +
psycopg2/dotenv (main dependencies), so they run in CI without skips.
"""

from src.pipelines.ville_ideale.load import filter_known_communes
from src.pipelines.ville_ideale.preprocess import build_records, group_reviews
from src.pipelines.ville_ideale.process import enrich, tokenize, word_cloud


def _review(code, rid, pos="", neg=""):
    return {
        "code_commune": code,
        "nom_ville": "X",
        "review_id": rid,
        "pseudonyme": "bob",
        "date_avis": "2026-01-01T10:00",
        "note_moyenne": 7.0,
        "notes": {"environnement": 8},
        "points_positifs": pos,
        "points_negatifs": neg,
        "nb_accord": 1,
        "nb_pas_accord": 0,
        "date_scraping": "2026-06-25",
    }


def _city(code, **extra):
    base = {"code_commune": code, "nom_ville": "Angers", "note_globale": 7.0, "notes": {"environnement": 8.0}}
    base.update(extra)
    return base


# ── preprocess ────────────────────────────────────────────────────────────────


def test_group_reviews_dedups_on_review_id():
    grouped = group_reviews([_review("49007", "1"), _review("49007", "1"), _review("49007", "2")])
    assert len(grouped["49007"]) == 2


def test_build_records_nests_reviews_and_strips_redundant_keys():
    records = build_records([_city("49007")], [_review("49007", "1")])
    assert len(records) == 1
    rec = records[0]
    assert rec["nb_avis"] == 1
    assert "code_commune" not in rec["avis"][0]  # stripped from the nested review
    assert rec["avis"][0]["review_id"] == "1"


def test_build_records_city_without_reviews():
    records = build_records([_city("49007")], [])
    assert records[0]["nb_avis"] == 0
    assert records[0]["avis"] == []


# ── process (word cloud) ──────────────────────────────────────────────────────


def test_tokenize_filters_stopwords_and_short_words():
    assert tokenize("La ville est calme et agréable") == ["calme", "agréable"]


def test_word_cloud_counts_and_orders():
    cloud = word_cloud(["transports pratiques", "transports rapides"], top_n=5)
    assert cloud[0] == {"mot": "transports", "frequence": 2}


def test_enrich_adds_word_cloud_per_commune():
    records = build_records([_city("49007")], [_review("49007", "1", pos="commerces nombreux", neg="commerces chers")])
    enrich(records)
    cloud = {e["mot"]: e["frequence"] for e in records[0]["word_cloud"]}
    assert cloud["commerces"] == 2


# ── load (FK guard) ───────────────────────────────────────────────────────────


def test_filter_known_communes_drops_unknown_codes():
    records = [_city("49007"), _city("99999")]
    kept, dropped = filter_known_communes(records, valid_codes={"49007"})
    assert [r["code_commune"] for r in kept] == ["49007"]
    assert dropped == ["99999"]
