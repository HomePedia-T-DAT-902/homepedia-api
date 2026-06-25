"""Scrapy spider for ville-ideale.fr — French city ratings and reviews.

Source   : https://www.ville-ideale.fr (participatory city-rating platform).
Volume   : ~91k reviews across ~8,500 cities; 9 criteria rated 0-10 plus free text.
Join key : the numeric code in each city URL is the INSEE ``code_commune`` (5 chars),
           which joins directly with every other Homepedia data source.

robots.txt: scraping this host is disallowed for ``User-agent: *`` but is an explicit
assignment requirement; we scrape politely and with robots obedience disabled. The full
rationale lives in ``settings.py`` — read it before changing the politeness settings.

Crawl flow
----------
1. GET  /villespardepts.php           -> department codes (and sets the PHPSESSID cookie)
2. POST /scripts/cherche.php dept=XX   -> city links ``/{slug}_{insee}`` for that department
3. GET  /{slug}_{insee}                -> aggregated notes + first page of reviews
4. GET  /{slug}_{insee}?page=N         -> remaining review pages

Output (written by the pipeline, gitignored under data/raw/ville_ideale/):
    cities.jsonl   -> one CityItem per rated commune
    reviews.jsonl  -> one ReviewItem per individual review

Usage
-----
    # Full crawl (long but polite):
    scrapy crawl villeideale

    # Resumable full crawl (survives interruption — re-run the same command to resume):
    scrapy crawl villeideale -s JOBDIR=data/raw/ville_ideale/jobdir

    # Scoped test run (a couple of communes, a couple of review pages):
    scrapy crawl villeideale -a depts=49 -a max_cities=2 -a max_review_pages=2
"""

import datetime as dt
import re

import scrapy

from src.sources.ville_ideale.scraper.items import CityItem, ReviewItem

BASE_URL = "https://www.ville-ideale.fr"

# The 9 criteria always appear in this fixed order, both in the city summary table
# (#tablonotes) and in each individual review table, so we map them by position.
CRITERIA = [
    "environnement",
    "transports",
    "securite",
    "sante",
    "sports_loisirs",
    "culture",
    "enseignement",
    "commerces",
    "qualite_vie",
]

# Trailing INSEE code in a city URL: 5 chars, allowing Corsica's 2A/2B (e.g. 2A004).
INSEE_RE = re.compile(r"_([0-9AB]{5})$")


def _to_float(text):
    """Convert a French-formatted number to a float.

    Args:
        text: A string such as ``"7,85"`` (comma decimal separator), or None.

    Returns:
        The parsed float, or None if ``text`` is empty or not numeric.
    """
    if not text:
        return None
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        return None


def _parse_review_date(text):
    """Parse a review's posting date into an ISO string.

    Args:
        text: The raw label, e.g. ``"Avis posté le 21-03-2026 à 10:47"``.

    Returns:
        ``"2026-03-21T10:47"`` when a time is present, ``"2026-03-21"`` when only a
        date is found, or None when no date can be parsed.
    """
    if not text:
        return None
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})(?:\s*à\s*(\d{2}):(\d{2}))?", text)
    if not m:
        return None
    day, month, year, hour, minute = m.groups()
    if hour is not None:
        return f"{year}-{month}-{day}T{hour}:{minute}"
    return f"{year}-{month}-{day}"


class VilleIdealeSpider(scrapy.Spider):
    name = "villeideale"
    allowed_domains = ["ville-ideale.fr"]

    def __init__(self, depts=None, codes=None, max_cities=None, max_review_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional arguments to scope a test run (all None => full crawl).
        #   depts=49,75        -> only these departments (case-insensitive: 2a == 2A)
        #   codes=49007        -> only these INSEE communes (great for targeted re-scrapes)
        #   max_cities=2       -> stop after N cities
        #   max_review_pages=2 -> at most N review pages per city
        self.depts_filter = {d.strip().upper() for d in depts.split(",")} if depts else None
        self.codes_filter = {c.strip().upper() for c in codes.split(",")} if codes else None
        self.max_cities = int(max_cities) if max_cities else None
        self.max_review_pages = int(max_review_pages) if max_review_pages else None
        self.cities_seen = 0
        self.scrape_date = dt.date.today().isoformat()

    async def start(self):
        # Entry point (Scrapy 2.13+ async API). This first GET also sets the PHPSESSID
        # cookie that the cherche.php department-list endpoint requires.
        yield scrapy.Request(
            f"{BASE_URL}/villespardepts.php",
            callback=self.parse_dept_index,
            errback=self._on_request_error,
        )

    def parse_dept_index(self, response):
        """Extract department codes from the affdept('01', 'Ain') onclick handlers."""
        codes = list(dict.fromkeys(re.findall(r"affdept\('([^']+)'", response.text)))
        if self.depts_filter:
            codes = [c for c in codes if c.upper() in self.depts_filter]
        self.logger.info("Departments to crawl: %d", len(codes))
        for code in codes:
            yield self._dept_request(code)

    def _dept_request(self, dept, refreshed=False):
        """Build the AJAX POST that returns a department's city list.

        Args:
            dept: Two/three-char department code (e.g. ``"49"``, ``"2A"``, ``"974"``).
            refreshed: True when this is a retry issued after refreshing the session
                cookie, used to avoid infinite refresh loops.

        Returns:
            A configured ``scrapy.FormRequest``. The session cookie is carried
            automatically by Scrapy's cookies middleware.
        """
        return scrapy.FormRequest(
            f"{BASE_URL}/scripts/cherche.php",
            formdata={"dept": dept},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{BASE_URL}/villespardepts.php",
            },
            callback=self.parse_dept_cities,
            cb_kwargs={"dept": dept, "refreshed": refreshed},
            dont_filter=refreshed,  # allow the retry to bypass the duplicate filter
            errback=self._on_request_error,
        )

    def parse_dept_cities(self, response, dept, refreshed=False):
        """Yield a request per city link (/{slug}_{insee}) in the department list.

        cherche.php needs a valid PHPSESSID; over a multi-hour crawl that session can
        expire, after which it returns an empty body. We detect the empty case, refresh
        the session once by re-fetching /villespardepts.php, and retry the department.
        """
        city_links = [
            (m.group(1), link) for link in response.css("a") if (m := INSEE_RE.search(link.attrib.get("href", "")))
        ]

        if not city_links:
            if not refreshed:
                self.logger.warning("dept=%s returned 0 cities — refreshing session and retrying", dept)
                yield scrapy.Request(
                    f"{BASE_URL}/villespardepts.php",
                    callback=self._refresh_then_retry_dept,
                    cb_kwargs={"dept": dept},
                    dont_filter=True,
                    errback=self._on_request_error,
                )
            else:
                self.logger.error("dept=%s still returned 0 cities after a session refresh — skipping", dept)
            return

        for code_commune, link in city_links:
            if self.max_cities is not None and self.cities_seen >= self.max_cities:
                return
            if self.codes_filter is not None and code_commune not in self.codes_filter:
                continue
            name = (link.css("::text").get() or "").replace("\xa0", " ").replace("‑", "-").strip()
            self.cities_seen += 1
            yield response.follow(
                link.attrib["href"],
                callback=self.parse_city,
                cb_kwargs={"code_commune": code_commune, "nom_ville": name},
                errback=self._on_request_error,
            )

    def _refresh_then_retry_dept(self, response, dept):
        """Re-issue a department city-list request after the session cookie is refreshed."""
        yield self._dept_request(dept, refreshed=True)

    def parse_city(self, response, code_commune, nom_ville):
        """Parse a city page: aggregated notes + first page of reviews."""
        notes = self._parse_summary_notes(response)
        note_globale = _to_float(response.css("#ng::text").get())

        # A commune can appear in the directory without any rating yet. Such pages still
        # render an empty #tablonotes (all dashes), so skip when there is no real rating.
        has_notes = bool(notes) and any(v is not None for v in notes.values())
        if note_globale is None and not has_notes:
            return

        rang, nb_villes = self._parse_rank(response)
        total_pages = self._parse_total_pages(response)

        page_reviews = list(self._parse_reviews(response, code_commune, nom_ville))
        yield from page_reviews

        if total_pages > 1 and not page_reviews:
            self.logger.warning(
                "City %s (%s) reports %d review pages but 0 reviews parsed on page 1 — possible markup change",
                code_commune,
                nom_ville,
                total_pages,
            )

        city_base = {
            "code_commune": code_commune,
            "nom_ville": nom_ville,
            "url": response.url,
            "note_globale": note_globale,
            "notes": notes,
            "rang": rang,
            "nb_villes_classees": nb_villes,
            "nb_pages_avis": total_pages,
            "date_scraping": self.scrape_date,
            "avis_complets": True,
        }

        last_page = total_pages
        if self.max_review_pages is not None:
            last_page = min(last_page, self.max_review_pages)

        if last_page > 1:
            # Walk the remaining review pages, threading the running review count so the
            # CityItem can be emitted (with an accurate nb_avis) on the last page. The
            # errback guarantees the CityItem is still emitted if a page request fails,
            # so its reviews are never orphaned.
            yield self._request_review_page(response.url, 2, city_base, last_page, len(page_reviews))
        else:
            city_base["nb_avis"] = len(page_reviews)
            yield self._build_city_item(city_base)

    def parse_review_page(self, response, city_base, page, last_page, reviews_count):
        """Parse review pages 2..N, then emit the CityItem on the final page."""
        page_reviews = list(self._parse_reviews(response, city_base["code_commune"], city_base["nom_ville"]))
        yield from page_reviews
        reviews_count += len(page_reviews)

        if page < last_page:
            yield self._request_review_page(response.url, page + 1, city_base, last_page, reviews_count)
        else:
            city_base["nb_avis"] = reviews_count
            yield self._build_city_item(city_base)

    # --- request helpers -------------------------------------------------------------

    def _request_review_page(self, current_url, page, city_base, last_page, reviews_count):
        base = current_url.split("?")[0]
        return scrapy.Request(
            f"{base}?page={page}#commentaires",
            callback=self.parse_review_page,
            cb_kwargs={
                "city_base": city_base,
                "page": page,
                "last_page": last_page,
                "reviews_count": reviews_count,
            },
            errback=self._on_review_page_error,
        )

    def _on_review_page_error(self, failure):
        """Emit the CityItem (flagged incomplete) when a review page ultimately fails.

        Without this, a failed intermediate page would break the request chain and the
        CityItem would never be emitted, leaving page-1 reviews orphaned in the output.
        """
        request = failure.request
        city_base = request.cb_kwargs["city_base"]
        city_base["nb_avis"] = request.cb_kwargs["reviews_count"]
        city_base["avis_complets"] = False
        self.logger.warning(
            "Review page failed for %s (%s) — emitting city with %d partial reviews: %s",
            city_base["code_commune"],
            failure.value.__class__.__name__,
            city_base["nb_avis"],
            request.url,
        )
        yield self._build_city_item(city_base)

    def _on_request_error(self, failure):
        """Log any request that fails after Scrapy exhausts its retries (no silent drops)."""
        self.logger.error("Request failed (%s): %s", failure.value.__class__.__name__, failure.request.url)

    def _build_city_item(self, city_base):
        return CityItem(
            code_commune=city_base["code_commune"],
            nom_ville=city_base["nom_ville"],
            url=city_base["url"],
            note_globale=city_base["note_globale"],
            nb_avis=city_base["nb_avis"],
            nb_pages_avis=city_base["nb_pages_avis"],
            notes=city_base["notes"],
            rang=city_base["rang"],
            nb_villes_classees=city_base["nb_villes_classees"],
            avis_complets=city_base["avis_complets"],
            date_scraping=city_base["date_scraping"],
        )

    # --- page parsing ----------------------------------------------------------------

    def _parse_summary_notes(self, response):
        """Read the #tablonotes summary table.

        Returns:
            A ``{criterion: average_float}`` dict, or None when the table is absent.
            A warning is logged if the cell count is not the expected 9.
        """
        values = response.css("#tablonotes td::text").getall()
        if not values:
            return None
        if len(values) != len(CRITERIA):
            self.logger.warning(
                "#tablonotes has %d cells, expected %d — markup may have changed", len(values), len(CRITERIA)
            )
        return {crit: _to_float(val) for crit, val in zip(CRITERIA, values)}

    def _parse_rank(self, response):
        """Best-effort rank parse: '... classée 19ème / 239 ... sur 8570 villes notées'.

        Returns:
            A ``(rang, nb_villes)`` tuple, e.g. ``("19/239", 8570)``; either element is
            None when not found.
        """
        txt = " ".join(response.css("#classt ::text").getall())
        rang = None
        nb_villes = None
        m = re.search(r"(\d+)\s*ème\s*/\s*(\d+)", txt)
        if m:
            rang = f"{m.group(1)}/{m.group(2)}"
        m = re.search(r"sur\s*([\d\s\xa0]+?)\s*villes", txt)
        if m:
            nb_villes = int(re.sub(r"[\s\xa0]", "", m.group(1)))
        return rang, nb_villes

    def _parse_total_pages(self, response):
        """Read the 'Page : 1 / N' header above the reviews.

        Returns:
            The total number of review pages (int); defaults to 1 when not found.
        """
        m = re.search(r"Page\s*:\s*\d+\s*/\s*(\d+)", response.text)
        return int(m.group(1)) if m else 1

    def _parse_reviews(self, response, code_commune, nom_ville):
        """Yield a ReviewItem for each .comm block on the current page."""
        for comm in response.css("div.comm"):
            header = comm.xpath("./p[1]")
            date_text = header.css("span::text").get()
            pseudo = header.css("strong::text").get()

            # This review's own average is plain-dotted in the markup (e.g. "7.44").
            note_moyenne = _to_float(comm.css("strong.moyenne::text").get())

            # The first inner table holds the 9 per-review notes in fixed order.
            cells = comm.xpath(".//table[1]//td/text()").getall()
            if cells and len(cells) != len(CRITERIA):
                self.logger.debug(
                    "Review in %s has %d note cells, expected %d", code_commune, len(cells), len(CRITERIA)
                )
            review_notes = {}
            for crit, val in zip(CRITERIA, cells):
                try:
                    review_notes[crit] = int(val.strip())
                except (ValueError, AttributeError):
                    review_notes[crit] = None
                    self.logger.debug("Unparsable note %r for %s in %s", val, crit, code_commune)

            interact = comm.css("div.interact")
            like_counts = [t for t in interact.css("p strong::text").getall() if t.strip().isdigit()]

            yield ReviewItem(
                code_commune=code_commune,
                nom_ville=nom_ville,
                review_id=interact.attrib.get("id"),
                pseudonyme=(pseudo or "").strip() or None,
                date_avis=_parse_review_date(date_text),
                note_moyenne=note_moyenne,
                notes=review_notes,
                points_positifs=self._extract_points(comm, "positifs"),
                points_negatifs=self._extract_points(comm, "négatifs"),
                nb_accord=int(like_counts[0]) if len(like_counts) >= 1 else None,
                nb_pas_accord=int(like_counts[1]) if len(like_counts) >= 2 else None,
                date_scraping=self.scrape_date,
            )

    def _extract_points(self, comm, kind):
        """Extract the free text of the '<b>Les points {kind} :</b> ...' paragraph.

        Args:
            comm: The ``div.comm`` selector for one review.
            kind: Either ``"positifs"`` or ``"négatifs"``.

        Returns:
            The comment text with original line breaks preserved (joined by ``\\n``), or
            None when the paragraph is absent. The ``<b>`` label itself is excluded, but
            any other (possibly nested) text in the paragraph is kept.
        """
        p = comm.xpath(f'.//p[b[contains(., "points {kind}")]]')
        if not p:
            return None
        lines = [t.strip() for t in p.xpath(".//text()[not(ancestor::b)]").getall() if t.strip()]
        return "\n".join(lines) or None
