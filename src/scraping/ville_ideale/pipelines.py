"""Item pipeline for the ville-ideale.fr scraper.

Routes the two item types to two newline-delimited JSON files under
``data/raw/ville_ideale/`` (gitignored):

    cities.jsonl   <- CityItem
    reviews.jsonl  <- ReviewItem

JSONL is used (rather than a single JSON array) so the crawl can stream results to
disk and a long run can be interrupted without corrupting the output.

The database load (PostgreSQL JSONB) is a separate, later task (backlog P3-2) and is
intentionally not done here — this pipeline only persists raw scraped data.
"""

import os

from scrapy.exporters import JsonLinesItemExporter

from src.scraping.ville_ideale.items import CityItem, ReviewItem


class VilleIdealeExportPipeline:
    """Write CityItem and ReviewItem to separate JSONL files."""

    def __init__(self, output_dir: str, resume: bool):
        self.output_dir = output_dir
        self.resume = resume

    @classmethod
    def from_crawler(cls, crawler):
        # When the crawl is resumable (JOBDIR set), Scrapy persists the request queue and
        # duplicate filter, so we append to the existing output instead of truncating it.
        # A plain (no-JOBDIR) run truncates for a clean, reproducible result.
        return cls(
            output_dir=crawler.settings.get("VILLE_IDEALE_OUTPUT_DIR", "data/raw/ville_ideale"),
            resume=bool(crawler.settings.get("JOBDIR")),
        )

    def open_spider(self, spider=None):
        os.makedirs(self.output_dir, exist_ok=True)
        mode = "ab" if self.resume else "wb"  # append when resuming, truncate for a fresh run
        self._city_file = open(os.path.join(self.output_dir, "cities.jsonl"), mode)
        self._review_file = open(os.path.join(self.output_dir, "reviews.jsonl"), mode)
        self._city_exporter = JsonLinesItemExporter(self._city_file, encoding="utf-8", ensure_ascii=False)
        self._review_exporter = JsonLinesItemExporter(self._review_file, encoding="utf-8", ensure_ascii=False)
        self._city_exporter.start_exporting()
        self._review_exporter.start_exporting()

    def process_item(self, item, spider=None):
        if isinstance(item, CityItem):
            self._city_exporter.export_item(item)
        elif isinstance(item, ReviewItem):
            self._review_exporter.export_item(item)
        return item

    def close_spider(self, spider=None):
        self._city_exporter.finish_exporting()
        self._review_exporter.finish_exporting()
        self._city_file.close()
        self._review_file.close()
