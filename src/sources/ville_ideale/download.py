"""Stage 1/4 — download: scrape ville-ideale.fr into raw JSON Lines.

Runs the Scrapy spider and produces:
    data/raw/ville_ideale/cities.jsonl
    data/raw/ville_ideale/reviews.jsonl

The spider itself (politeness, session handling, parsing) lives in the Scrapy package
under ``src/scraping/ville_ideale``. This stage is a thin, importable entry point so the
pipeline can be driven uniformly (download -> preprocess -> process -> load).

Usage:
    python -m src.sources.ville_ideale.download                  # full crawl
    python -m src.sources.ville_ideale.download --depts 35       # one department
    python -m src.sources.ville_ideale.download --codes 35238    # specific communes
"""

import argparse
import logging
from pathlib import Path

from src.sources.ville_ideale import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run(
    raw_dir: Path = config.RAW_DIR,
    depts: str | None = None,
    codes: str | None = None,
    jobdir: str | None = None,
) -> None:
    """Run the ville-ideale Scrapy spider.

    Args:
        raw_dir: Output directory (the spider already writes here via its Scrapy settings;
            accepted for interface consistency with the other sources' download stage).
        depts: Comma-separated department codes to restrict to (e.g. ``"35,49"``).
        codes: Comma-separated INSEE codes to restrict to (e.g. ``"35238"``).
        jobdir: Optional Scrapy JOBDIR for a resumable crawl.
    """
    # Imported lazily so the rest of the pipeline does not require Scrapy installed.
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

    settings = get_project_settings()
    if jobdir:
        settings.set("JOBDIR", jobdir)

    process = CrawlerProcess(settings)
    process.crawl("villeideale", depts=depts, codes=codes)
    logger.info("Starting ville-ideale crawl (depts=%s, codes=%s)", depts, codes)
    process.start()  # blocks until the crawl finishes


def main() -> None:
    parser = argparse.ArgumentParser(description="Download (scrape) ville-ideale.fr reviews.")
    parser.add_argument("--depts", help="Comma-separated department codes (e.g. 35,49).")
    parser.add_argument("--codes", help="Comma-separated INSEE codes (e.g. 35238).")
    parser.add_argument("--jobdir", help="Scrapy JOBDIR for a resumable crawl.")
    args = parser.parse_args()
    run(depts=args.depts, codes=args.codes, jobdir=args.jobdir)


if __name__ == "__main__":
    main()
