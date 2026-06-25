"""Offline tests for the city_reviews loading logic (ville-ideale.fr).

Only the pure transform is exercised here (no database). ``postgres_loader`` imports
pandas/numpy (the optional ``bigdata`` group, not installed in CI), so the module is
skipped when those are unavailable.
"""

import json

import pytest

pytest.importorskip("pandas")
pytest.importorskip("numpy")

from src.database.postgres_loader import (  # noqa: E402
    build_city_review_rows,
    read_jsonl,
)


def test_read_jsonl_missing_file_returns_empty(tmp_path):
    assert read_jsonl(tmp_path / "nope.jsonl") == []


def test_read_jsonl_reads_all_lines(tmp_path):
    path = tmp_path / "cities.jsonl"
    path.write_text('{"a": 1}\n\n{"a": 2}\n', encoding="utf-8")
    assert read_jsonl(path) == [{"a": 1}, {"a": 2}]


def _city(code, **extra):
    base = {"code_commune": code, "note_globale": 7.0, "notes": {"environnement": 8.0}, "rang": "1/10"}
    base.update(extra)
    return base


def _review(code, rid):
    return {
        "code_commune": code,
        "nom_ville": "X",
        "review_id": rid,
        "pseudonyme": "bob",
        "date_avis": "2026-01-01T10:00",
        "note_moyenne": 7.0,
        "notes": {"environnement": 8},
        "points_positifs": "ok",
        "points_negatifs": "rien",
        "nb_accord": 1,
        "nb_pas_accord": 0,
        "date_scraping": "2026-06-25",
    }


def test_build_rows_groups_reviews_and_counts_nb_avis():
    cities = [_city("49007", avis_complets=True, date_scraping="2026-06-25")]
    reviews = [_review("49007", "1"), _review("49007", "2")]
    records, stats, dropped = build_city_review_rows(cities, reviews, valid_codes={"49007"})

    assert stats == {"cities_total": 1, "loaded": 1, "dropped_unknown": 0, "orphan_review_communes": 0}
    assert dropped == []
    row = records[0]
    assert row["code_commune"] == "49007"
    assert row["nb_avis"] == 2
    assert len(row["avis"]) == 2
    # Redundant per-review keys must be stripped from the embedded JSON.
    assert "code_commune" not in row["avis"][0]
    assert "nom_ville" not in row["avis"][0]
    assert row["avis"][0]["review_id"] == "1"


def test_build_rows_dedups_on_review_id():
    cities = [_city("49007")]
    reviews = [_review("49007", "1"), _review("49007", "1"), _review("49007", "2")]
    records, _, _ = build_city_review_rows(cities, reviews, valid_codes={"49007"})
    assert records[0]["nb_avis"] == 2  # the duplicate review_id "1" is dropped


def test_build_rows_filters_codes_absent_from_communes():
    """A commune scraped but not present in the communes reference is dropped (FK guard)."""
    cities = [_city("49007"), _city("99999")]  # 99999 = unknown / former commune
    reviews = [_review("49007", "1")]
    records, stats, dropped = build_city_review_rows(cities, reviews, valid_codes={"49007"})

    assert [r["code_commune"] for r in records] == ["49007"]
    assert dropped == ["99999"]
    assert stats["dropped_unknown"] == 1


def test_build_rows_counts_orphan_review_communes():
    """Reviews referencing a commune absent from cities.jsonl are reported, not loaded."""
    cities = [_city("49007")]
    reviews = [_review("49007", "1"), _review("12345", "9")]
    _, stats, _ = build_city_review_rows(cities, reviews, valid_codes={"49007"})
    assert stats["orphan_review_communes"] == 1


def test_build_rows_city_without_reviews_is_kept_with_zero():
    cities = [_city("49007")]
    records, _, _ = build_city_review_rows(cities, [], valid_codes={"49007"})
    assert records[0]["nb_avis"] == 0
    assert records[0]["avis"] == []


def test_records_are_json_serialisable():
    """The records must be plain JSON (no psycopg2 wrappers) so they stay testable."""
    cities = [_city("49007")]
    reviews = [_review("49007", "1")]
    records, _, _ = build_city_review_rows(cities, reviews, valid_codes={"49007"})
    json.dumps(records)  # must not raise
