"""Scrapy items for the ville-ideale.fr scraper.

Two item types are produced by the spider and routed to two JSONL files by the
pipeline (see pipelines.py):

- CityItem   : one row per rated commune (aggregated note + 9 average criteria).
- ReviewItem : one row per individual review (free text + 9 per-review notes).

Both carry ``code_commune`` (the INSEE code parsed from the city URL), which is the
universal join key with every other Homepedia data source.
"""

import scrapy


class CityItem(scrapy.Item):
    """Aggregated rating of a single commune."""

    code_commune = scrapy.Field()  # INSEE code (5 chars), e.g. "49007"
    nom_ville = scrapy.Field()
    url = scrapy.Field()
    note_globale = scrapy.Field()  # float, average of the 9 criteria (e.g. 7.85)
    nb_avis = scrapy.Field()  # int, total number of reviews collected
    nb_pages_avis = scrapy.Field()  # int, number of review pages on the site
    notes = scrapy.Field()  # dict[str, float] — 9 criteria averages
    rang = scrapy.Field()  # str, e.g. "19/239" (best-effort, may be None)
    nb_villes_classees = scrapy.Field()  # int, total ranked cities (best-effort)
    avis_complets = scrapy.Field()  # bool, False if a review page failed mid-crawl
    date_scraping = scrapy.Field()  # ISO date the page was scraped


class ReviewItem(scrapy.Item):
    """A single user review of a commune.

    Note: the data-source doc mentions a "statut" (habitant / ancien résident) field,
    but it is not exposed in the current page markup, so it is intentionally omitted.
    """

    code_commune = scrapy.Field()
    nom_ville = scrapy.Field()
    review_id = scrapy.Field()  # site-internal id of the comment (str)
    pseudonyme = scrapy.Field()
    date_avis = scrapy.Field()  # ISO datetime, e.g. "2026-03-21T10:47"
    note_moyenne = scrapy.Field()  # float, this review's own average (e.g. 7.44)
    notes = scrapy.Field()  # dict[str, int] — 9 per-review notes (0-10)
    points_positifs = scrapy.Field()  # free text
    points_negatifs = scrapy.Field()  # free text
    nb_accord = scrapy.Field()  # int, "d'accord" votes (best-effort)
    nb_pas_accord = scrapy.Field()  # int, "pas d'accord" votes (best-effort)
    date_scraping = scrapy.Field()
