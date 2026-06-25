"""On-demand single-commune fetch for ville-ideale.fr (lazy loading for the API).

When the API gets a cache miss for a commune, it fetches just that commune's page with
``requests`` — not the Scrapy bulk crawler — parses the summary + first page of reviews,
computes a word cloud, and returns a record the API stores in ``city_reviews``. Reviews
are thus scraped lazily as users browse: a trickle of requests instead of one massive
crawl that gets rate-limited.

The commune URL is ``/{slug}_{insee}``; the slug is resolved (and cached per department)
from the cherche.php department list, so we never have to guess it from the name.

Parsing mirrors the Scrapy spider's selectors but is kept Scrapy-free here so the API can
import it without the (optional) scraping dependencies.
"""

import datetime as dt
import re

import requests
from parsel import Selector

from src.pipelines.ville_ideale.process import word_cloud

BASE_URL = "https://www.ville-ideale.fr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HomepediaBot/0.1; +https://github.com/HomePedia-T-DAT-902)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

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

INSEE_RE = re.compile(r"_([0-9AB]{5})$")
MIN_CONTENT_BYTES = 200  # below this, the response is the site's empty rate-limit stub
TIMEOUT = 15

# In-process cache of {dept: {code_commune: "/slug_code"}} so each department list is
# fetched at most once.
_dept_cache: dict[str, dict[str, str]] = {}


class ThrottledError(RuntimeError):
    """Raised when ville-ideale returns its empty rate-limit stub instead of content."""


def _to_float(text):
    if not text:
        return None
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        return None


def _parse_review_date(text):
    if not text:
        return None
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})(?:\s*à\s*(\d{2}):(\d{2}))?", text)
    if not m:
        return None
    day, month, year, hour, minute = m.groups()
    return f"{year}-{month}-{day}T{hour}:{minute}" if hour is not None else f"{year}-{month}-{day}"


def _dept_of(code_commune: str) -> str:
    """Department code for an INSEE commune code (handles Corsica 2A/2B and the DOM)."""
    if code_commune[:2] in ("2A", "2B"):
        return code_commune[:2]
    if code_commune.startswith("97"):
        return code_commune[:3]
    return code_commune[:2]


def _extract_points(comm, kind):
    p = comm.xpath(f'.//p[b[contains(., "points {kind}")]]')
    if not p:
        return None
    lines = [t.strip() for t in p.xpath(".//text()[not(ancestor::b)]").getall() if t.strip()]
    return "\n".join(lines) or None


def parse_dept_list(html: str) -> dict[str, str]:
    """Map ``{code_commune: '/slug_code'}`` from a cherche.php department fragment."""
    out = {}
    for href in Selector(text=html).css("a::attr(href)").getall():
        m = INSEE_RE.search(href)
        if m:
            out[m.group(1)] = href
    return out


def _parse_reviews(sel) -> list[dict]:
    reviews = []
    for comm in sel.css("div.comm"):
        header = comm.xpath("./p[1]")
        cells = comm.xpath(".//table[1]//td/text()").getall()
        notes = {}
        for crit, val in zip(CRITERIA, cells):
            try:
                notes[crit] = int(val.strip())
            except (ValueError, AttributeError):
                notes[crit] = None
        interact = comm.css("div.interact")
        likes = [t for t in interact.css("p strong::text").getall() if t.strip().isdigit()]
        reviews.append(
            {
                "review_id": interact.attrib.get("id"),
                "pseudonyme": (header.css("strong::text").get() or "").strip() or None,
                "date_avis": _parse_review_date(header.css("span::text").get()),
                "note_moyenne": _to_float(comm.css("strong.moyenne::text").get()),
                "notes": notes,
                "points_positifs": _extract_points(comm, "positifs"),
                "points_negatifs": _extract_points(comm, "négatifs"),
                "nb_accord": int(likes[0]) if len(likes) >= 1 else None,
                "nb_pas_accord": int(likes[1]) if len(likes) >= 2 else None,
            }
        )
    return reviews


def parse_commune(html: str) -> dict | None:
    """Parse a commune page into a city_reviews record, or None if the commune is unrated.

    Only the first page of reviews is parsed (on-demand favours a fast single request);
    ``nb_pages_avis`` records the true number of review pages available on the site.
    """
    sel = Selector(text=html)
    note_values = sel.css("#tablonotes td::text").getall()
    note_globale = _to_float(sel.css("#ng::text").get())
    notes = {crit: _to_float(v) for crit, v in zip(CRITERIA, note_values)} if note_values else None

    has_notes = bool(notes) and any(v is not None for v in notes.values())
    if note_globale is None and not has_notes:
        return None

    rang = None
    classt = " ".join(sel.css("#classt ::text").getall())
    m = re.search(r"(\d+)\s*ème\s*/\s*(\d+)", classt)
    if m:
        rang = f"{m.group(1)}/{m.group(2)}"

    m = re.search(r"Page\s*:\s*\d+\s*/\s*(\d+)", html)
    total_pages = int(m.group(1)) if m else 1

    reviews = _parse_reviews(sel)
    texts = [t for r in reviews for t in (r["points_positifs"], r["points_negatifs"])]

    return {
        "note_globale": note_globale,
        "nb_avis": len(reviews),
        "nb_pages_avis": total_pages,
        "notes": notes,
        "avis": reviews,
        "word_cloud": word_cloud(texts),
        "rang": rang,
        "avis_complets": total_pages <= 1,  # only page 1 is fetched on demand
        "date_scraping": dt.date.today().isoformat(),
    }


def _check_not_throttled(response) -> None:
    if len(response.content) < MIN_CONTENT_BYTES:
        raise ThrottledError(f"Empty/throttled response from ville-ideale for {response.url}")


def resolve_url(code_commune: str, session: requests.Session) -> str | None:
    """Resolve a commune's full URL, fetching (and caching) its department list if needed."""
    dept = _dept_of(code_commune)
    if dept not in _dept_cache:
        session.get(f"{BASE_URL}/villespardepts.php", timeout=TIMEOUT)  # primes the PHPSESSID cookie
        resp = session.post(
            f"{BASE_URL}/scripts/cherche.php",
            data={"dept": dept},
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE_URL}/villespardepts.php"},
            timeout=TIMEOUT,
        )
        _check_not_throttled(resp)
        _dept_cache[dept] = parse_dept_list(resp.text)
    path = _dept_cache[dept].get(code_commune)
    return f"{BASE_URL}{path}" if path else None


def fetch_commune(code_commune: str) -> dict | None:
    """Fetch and parse one commune on demand.

    Returns a city_reviews record (with ``code_commune`` set), or None if the commune is
    unknown on the site or has no rating. Raises ``ThrottledError`` if rate-limited.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    url = resolve_url(code_commune, session)
    if url is None:
        return None
    resp = session.get(url, timeout=TIMEOUT)
    _check_not_throttled(resp)
    record = parse_commune(resp.text)
    if record is None:
        return None
    record["code_commune"] = code_commune
    return record
