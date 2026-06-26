"""Offline tests for the on-demand single-commune fetcher (parsing + throttle detection)."""

from types import SimpleNamespace

import pytest

from src.sources.ville_ideale.on_demand import (
    ThrottledError,
    _check_not_throttled,
    _dept_of,
    fetch_commune,  # noqa: F401  (import smoke-tests the module loads)
    parse_commune,
    parse_dept_list,
)

DEPT_FRAGMENT = (
    '<p><span>A</span> <a href="/allonnes_49002">Allonnes</a> '
    '<a href="/angers_49007">Angers</a> <a href="/classements.php">x</a></p>'
)

CITY_PAGE = """
<html><body>
  <p id="classt"><strong>Angers</strong> est <a>classée <b>19ème / 239</b></a> sur <b>8570 villes</b>.</p>
  <p id="ng">7,85<span> / 10</span></p>
  <table id="tablonotes">
    <tr><th>Env</th><td>8,02</td></tr><tr><th>Tra</th><td>7,28</td></tr>
    <tr><th>Sec</th><td>6,85</td></tr><tr><th>San</th><td>8,15</td></tr>
    <tr><th>Spo</th><td>8,06</td></tr><tr><th>Cul</th><td>7,88</td></tr>
    <tr><th>Ens</th><td>8,06</td></tr><tr><th>Com</th><td>7,73</td></tr>
    <tr><th>QV</th><td>7,94</td></tr>
  </table>
  <h4>Page : 1 / 3</h4>
  <div class="comm">
    <p><span>Avis posté le 21-03-2026 à 10:47</span><br/>Par <strong>Stevendeb</strong></p>
    <strong class="moyenne">7.44</strong>
    <table><tr><th>x</th></tr><tr>
      <td>9</td><td>10</td><td>5</td><td>6</td><td>3</td><td>3</td><td>5</td><td>6</td><td>9</td>
    </tr></table>
    <p><b>Les points positifs : </b>Ville verte, transports efficaces.</p>
    <p><b>Les points négatifs : </b>Travaux.</p>
    <div class="interact" id="131042"><p><strong>67</strong><strong>174</strong></p></div>
  </div>
</body></html>
"""


@pytest.mark.parametrize(
    ("code", "dept"),
    [("49007", "49"), ("35238", "35"), ("2A004", "2A"), ("2B033", "2B"), ("97411", "974")],
)
def test_dept_of(code, dept):
    assert _dept_of(code) == dept


def test_parse_dept_list_maps_codes_to_paths():
    mapping = parse_dept_list(DEPT_FRAGMENT)
    assert mapping == {"49002": "/allonnes_49002", "49007": "/angers_49007"}


def test_parse_commune_extracts_summary_reviews_and_word_cloud():
    record = parse_commune(CITY_PAGE)
    assert record["note_globale"] == 7.85
    assert record["notes"]["environnement"] == 8.02
    assert record["notes"]["qualite_vie"] == 7.94
    assert record["rang"] == "19/239"
    assert record["nb_pages_avis"] == 3
    assert record["avis_complets"] is False  # 3 pages exist, we only fetched page 1
    assert record["nb_avis"] == 1
    review = record["avis"][0]
    assert review["pseudonyme"] == "Stevendeb"
    assert review["notes"]["transports"] == 10
    assert "points positifs" not in review["points_positifs"]
    cloud = {e["mot"] for e in record["word_cloud"]}
    assert "transports" in cloud


def test_parse_commune_returns_none_for_unrated():
    unrated = '<html><body><p id="ng"><span>/ 10</span></p>'
    unrated += '<table id="tablonotes"><tr><th>Env</th><td>-</td></tr></table></body></html>'
    assert parse_commune(unrated) is None


def test_check_not_throttled_raises_on_tiny_body():
    with pytest.raises(ThrottledError):
        _check_not_throttled(SimpleNamespace(content=b"\n", url="https://www.ville-ideale.fr/x"))


def test_check_not_throttled_passes_on_full_body():
    _check_not_throttled(SimpleNamespace(content=b"x" * 5000, url="https://www.ville-ideale.fr/x"))
