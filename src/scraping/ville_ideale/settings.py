"""Scrapy settings for the ville-ideale.fr scraper.

robots.txt decision (read this before changing ROBOTSTXT_OBEY)
--------------------------------------------------------------
ville-ideale.fr's robots.txt whitelists a handful of search-engine crawlers and
disallows ``User-agent: *`` on the entire site. Scraping this source is nonetheless
an explicit requirement of the T-DAT-902 assignment, the data has no public API, and
the total volume is small (~8,500 city pages). We therefore disable robots obedience
deliberately and compensate with strict, conservative politeness:

- a single request at a time (no parallelism against the host),
- a 2-3s randomized delay plus AutoThrottle,
- an identified User-Agent carrying a contact URL,
- a local HTTP cache so development re-runs do not re-hit the server.

This is a documented, intentional decision — not an oversight.
"""

from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    """Walk up from ``start`` to the directory containing pyproject.toml (the repo root).

    This is more robust than a hardcoded ``parents[N]`` if the package is ever moved or
    nested differently. Falls back to the historical 4-levels-up location.
    """
    for parent in (start, *start.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return start.parents[3]


_REPO_ROOT = _find_repo_root(Path(__file__).resolve())
_OUTPUT_DIR = _REPO_ROOT / "data" / "raw" / "ville_ideale"

BOT_NAME = "homepedia_ville_ideale"

SPIDER_MODULES = ["src.scraping.ville_ideale.spiders"]
NEWSPIDER_MODULE = "src.scraping.ville_ideale.spiders"

# Identified bot with a contact URL (politeness / transparency).
USER_AGENT = "Mozilla/5.0 (compatible; HomepediaBot/0.1; +https://github.com/HomePedia-T-DAT-902)"

# See the module docstring for the rationale behind disabling robots obedience.
ROBOTSTXT_OBEY = False

# --- Politeness: one request at a time, conservative delay, adaptive throttling ---
# The site rate-limits aggressive clients by serving empty HTTP 200 stubs (see
# middlewares.ThrottleRetryMiddleware). Keep the crawl slow to avoid tripping that limit;
# combine with -s JOBDIR=... to resume a large crawl across sessions if it does trip.
CONCURRENT_REQUESTS = 1
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 3.0
RANDOMIZE_DOWNLOAD_DELAY = True

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 3.0
AUTOTHROTTLE_MAX_DELAY = 30.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

# Retry transient failures, including the site's empty rate-limit responses, with back-off.
RETRY_ENABLED = True
RETRY_TIMES = 4

# Detect and retry the empty 200 "throttle stub" responses (see middlewares.py).
DOWNLOADER_MIDDLEWARES = {
    "src.scraping.ville_ideale.middlewares.ThrottleRetryMiddleware": 555,
}

# cherche.php (the per-department city list) requires a PHPSESSID cookie, which the
# first GET to /villespardepts.php sets. The cookies middleware carries it forward.
COOKIES_ENABLED = True

# Send browser-like headers (a missing Accept header makes some servers reply oddly).
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# Local on-disk HTTP cache: re-runs during development reuse cached pages instead of
# hammering the site. Lives under the gitignored data/ tree. Delete it to force-refresh.
HTTPCACHE_ENABLED = True
HTTPCACHE_DIR = str(_OUTPUT_DIR / "httpcache")  # absolute -> stays under gitignored data/
HTTPCACHE_EXPIRATION_SECS = 60 * 60 * 24 * 7  # 1 week
HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504, 408, 429]

ITEM_PIPELINES = {
    "src.scraping.ville_ideale.pipelines.VilleIdealeExportPipeline": 300,
}

# Directory where the pipeline writes cities.jsonl / reviews.jsonl (gitignored).
VILLE_IDEALE_OUTPUT_DIR = str(_OUTPUT_DIR)

LOG_LEVEL = "INFO"
FEED_EXPORT_ENCODING = "utf-8"

# Use the modern request fingerprinter / async reactor (silences deprecation warnings).
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
