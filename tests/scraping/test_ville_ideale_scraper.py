"""Offline tests for the ville-ideale.fr scraper.

These tests run against small embedded HTML fixtures (no network) so they are fast and
deterministic. The ``scrapy`` dependency lives in the optional ``scraping`` group, which
CI does not install, so the whole module is skipped when Scrapy is unavailable.
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("scrapy")

from scrapy.http import HtmlResponse  # noqa: E402

from src.scraping.ville_ideale.items import CityItem, ReviewItem  # noqa: E402
from src.scraping.ville_ideale.spiders.reviews_spider import (  # noqa: E402
    INSEE_RE,
    VilleIdealeSpider,
    _parse_review_date,
    _to_float,
)


def _response(body: str, url: str = "https://www.ville-ideale.fr/angers_49007") -> HtmlResponse:
    """Wrap an HTML fragment in an HtmlResponse so spider selectors can run on it."""
    return HtmlResponse(url=url, body=body.encode("utf-8"), encoding="utf-8")


# A representative single review block, modelled on the real ville-ideale.fr markup.
REVIEW_BLOCK = """
<div class="comm">
  <p><span>Avis posté le 21-03-2026 à 10:47</span><br/>Par <strong>Stevendeb</strong></p>
  <strong class="moyenne">7.44</strong>
  <table>
    <tr><th>Env</th><th>Tra</th><th>Sec</th><th>San</th><th>Spo</th><th>Cul</th><th>Ens</th><th>Com</th><th>QV</th></tr>
    <tr><td class="vert">9</td><td class="vert">10</td><td class="bleu">5</td><td class="bleu">6</td>
        <td class="rouge">3</td><td class="rouge">3</td><td class="bleu">5</td><td class="bleu">6</td>
        <td class="vert">9</td></tr>
  </table>
  <p><b>Les points positifs : </b>Première ligne.<br/>Deuxième ligne.</p>
  <p><b>Les points négatifs : </b>Trop de travaux.</p>
  <div class="interact" id="131042"><p><strong>67</strong><strong>174</strong></p></div>
</div>
"""

# A minimal single-page city: global note, the 9-criteria table, a rank line, one review.
CITY_PAGE = f"""
<html><body>
  <p id="classt"><strong>Angers</strong> est <a>classée <b>19ème / 239</b></a> sur <b>8570 villes notées</b>.</p>
  <p id="ng" style="background-color: #99AD00">7,85<span> / 10</span></p>
  <table id="tablonotes">
    <tr><th>Environnement</th><td>8,02</td></tr>
    <tr><th>Transports</th><td>7,28</td></tr>
    <tr><th>Sécurité</th><td>6,85</td></tr>
    <tr><th>Santé</th><td>8,15</td></tr>
    <tr><th>Sports</th><td>8,06</td></tr>
    <tr><th>Culture</th><td>7,88</td></tr>
    <tr><th>Enseignement</th><td>8,06</td></tr>
    <tr><th>Commerces</th><td>7,73</td></tr>
    <tr><th>Qualité de vie</th><td>7,94</td></tr>
  </table>
  <h4>Page : 1 / 1</h4>
  {REVIEW_BLOCK}
</body></html>
"""


# ── helper functions ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [("7,85", 7.85), ("7.44", 7.44), ("  6,0 ", 6.0), ("", None), (None, None), ("n/a", None)],
)
def test_to_float(text, expected):
    assert _to_float(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Avis posté le 21-03-2026 à 10:47", "2026-03-21T10:47"),
        ("Avis posté le 02-02-2026", "2026-02-02"),
        ("pas de date", None),
        (None, None),
    ],
)
def test_parse_review_date(text, expected):
    assert _parse_review_date(text) == expected


@pytest.mark.parametrize(
    ("href", "ok"),
    [
        ("/angers_49007", True),
        ("/ajaccio_2A004", True),
        ("/saint-denis_97411", True),
        ("/classements.php", False),
        ("/villespardepts.php", False),
        ("/index.php", False),
    ],
)
def test_insee_regex(href, ok):
    assert bool(INSEE_RE.search(href)) is ok


# ── page parsing ──────────────────────────────────────────────────────────────


def test_parse_summary_notes_maps_nine_criteria():
    spider = VilleIdealeSpider()
    notes = spider._parse_summary_notes(_response(CITY_PAGE))
    assert notes["environnement"] == 8.02
    assert notes["securite"] == 6.85
    assert notes["qualite_vie"] == 7.94
    assert len(notes) == 9


def test_parse_reviews_extracts_all_fields():
    spider = VilleIdealeSpider()
    reviews = list(spider._parse_reviews(_response(REVIEW_BLOCK), "49007", "Angers"))
    assert len(reviews) == 1
    r = reviews[0]
    assert r["pseudonyme"] == "Stevendeb"
    assert r["date_avis"] == "2026-03-21T10:47"
    assert r["note_moyenne"] == 7.44
    assert r["review_id"] == "131042"
    assert r["notes"] == {
        "environnement": 9,
        "transports": 10,
        "securite": 5,
        "sante": 6,
        "sports_loisirs": 3,
        "culture": 3,
        "enseignement": 5,
        "commerces": 6,
        "qualite_vie": 9,
    }
    assert r["nb_accord"] == 67
    assert r["nb_pas_accord"] == 174


def test_extract_points_keeps_lines_and_drops_label():
    spider = VilleIdealeSpider()
    review = next(spider._parse_reviews(_response(REVIEW_BLOCK), "49007", "Angers"))
    # The "<b>Les points positifs :</b>" label must be excluded; both lines preserved.
    assert review["points_positifs"] == "Première ligne.\nDeuxième ligne."
    assert "points positifs" not in review["points_positifs"]
    assert review["points_negatifs"] == "Trop de travaux."


def test_parse_city_emits_city_and_reviews():
    spider = VilleIdealeSpider()
    out = list(spider.parse_city(_response(CITY_PAGE), "49007", "Angers"))
    reviews = [o for o in out if isinstance(o, ReviewItem)]
    cities = [o for o in out if isinstance(o, CityItem)]
    assert len(reviews) == 1
    assert len(cities) == 1
    city = cities[0]
    assert city["note_globale"] == 7.85
    assert city["nb_avis"] == 1
    assert city["nb_pages_avis"] == 1
    assert city["rang"] == "19/239"
    assert city["nb_villes_classees"] == 8570
    assert city["avis_complets"] is True


def test_parse_city_skips_unrated_commune():
    """A commune in the directory but never rated yields nothing."""
    unrated = """
    <html><body>
      <p id="ng"><span> / 10</span></p>
      <table id="tablonotes">
        <tr><th>Environnement</th><td>-</td></tr><tr><th>Transports</th><td>-</td></tr>
      </table>
    </body></html>
    """
    spider = VilleIdealeSpider()
    assert list(spider.parse_city(_response(unrated), "49005", "Andigné")) == []


# ── resilience: critical fix ──────────────────────────────────────────────────


def test_errback_emits_city_when_review_page_fails():
    """A failed review page must still emit the CityItem, flagged incomplete."""
    spider = VilleIdealeSpider()
    city_base = {
        "code_commune": "49007",
        "nom_ville": "Angers",
        "url": "https://www.ville-ideale.fr/angers_49007",
        "note_globale": 7.85,
        "notes": {"environnement": 8.02},
        "rang": "19/239",
        "nb_villes_classees": 8570,
        "nb_pages_avis": 34,
        "date_scraping": "2026-06-25",
        "avis_complets": True,
    }
    failure = SimpleNamespace(
        request=SimpleNamespace(
            url="https://www.ville-ideale.fr/angers_49007?page=3",
            cb_kwargs={"city_base": city_base, "page": 3, "last_page": 34, "reviews_count": 12},
        ),
        value=TimeoutError("simulated"),
    )
    emitted = list(spider._on_review_page_error(failure))
    assert len(emitted) == 1
    assert isinstance(emitted[0], CityItem)
    assert emitted[0]["avis_complets"] is False
    assert emitted[0]["nb_avis"] == 12
