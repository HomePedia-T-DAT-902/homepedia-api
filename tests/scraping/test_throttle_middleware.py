"""Offline tests for the ThrottleRetryMiddleware (rate-limit handling)."""

import logging
from types import SimpleNamespace

import pytest

pytest.importorskip("scrapy")

from scrapy.http import HtmlResponse, Request  # noqa: E402
from scrapy.settings import Settings  # noqa: E402
from scrapy.statscollectors import MemoryStatsCollector  # noqa: E402

from src.scraping.ville_ideale.middlewares import ThrottleRetryMiddleware  # noqa: E402


def _spider(retry_times=2):
    """A minimal spider stub exposing what get_retry_request needs (settings + stats)."""
    settings = Settings({"RETRY_TIMES": retry_times, "STATS_DUMP": False})
    crawler = SimpleNamespace(settings=settings)
    crawler.stats = MemoryStatsCollector(crawler)
    return SimpleNamespace(crawler=crawler, logger=logging.getLogger("test"))


def _response(body: bytes, url: str = "https://www.ville-ideale.fr/rennes_35238") -> HtmlResponse:
    return HtmlResponse(url=url, body=body, encoding="utf-8")


def test_full_response_passes_through_unchanged():
    mw = ThrottleRetryMiddleware()
    request = Request("https://www.ville-ideale.fr/rennes_35238")
    response = _response(b"<html>" + b"x" * 1000 + b"</html>")
    assert mw.process_response(request, response, _spider()) is response


def test_empty_throttle_stub_is_retried():
    mw = ThrottleRetryMiddleware()
    request = Request("https://www.ville-ideale.fr/rennes_35238")
    response = _response(b"\n")  # ~1 byte, well under the threshold
    out = mw.process_response(request, response, _spider())
    assert isinstance(out, Request)  # a retry request was scheduled
    assert out.meta.get("retry_times") == 1


def test_throttle_stub_gives_up_after_max_retries():
    mw = ThrottleRetryMiddleware()
    # Already at the retry ceiling -> no further retry, the response is returned.
    request = Request("https://www.ville-ideale.fr/rennes_35238", meta={"retry_times": 2})
    response = _response(b"")
    out = mw.process_response(request, response, _spider(retry_times=2))
    assert out is response
