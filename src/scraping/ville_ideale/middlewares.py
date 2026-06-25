"""Downloader middlewares for the ville-ideale scraper.

ville-ideale.fr rate-limits aggressive clients by answering HTTP 200 with an almost
empty body (~20 bytes, a fresh PHPSESSID, no content) instead of an error status. Left
unhandled, the spider parses that empty page, finds no ratings, and silently treats the
commune as "unrated" — turning throttling into massive, invisible data loss.

``ThrottleRetryMiddleware`` detects those contentless 200s and retries them through
Scrapy's standard retry machinery (with back-off). When the retries are exhausted it logs
an error, so a throttled page is never silently dropped.
"""

from scrapy.downloadermiddlewares.retry import get_retry_request

# Any 200 text/html response smaller than this is treated as a throttle stub. Real pages
# are several KB; the smallest legitimate fragment (a department's city list) is still
# multiple KB, so this threshold does not flag valid responses.
MIN_CONTENT_BYTES = 200


class ThrottleRetryMiddleware:
    """Retry contentless HTTP 200 responses (the site's rate-limit stub)."""

    def process_response(self, request, response, spider):
        if response.status == 200 and len(response.body) < MIN_CONTENT_BYTES:
            new_request = get_retry_request(
                request,
                spider=spider,
                reason="throttled (empty 200 response)",
            )
            if new_request is not None:
                return new_request
            # Retries exhausted: surface it loudly rather than letting the spider
            # mistake an empty body for an unrated commune.
            spider.logger.error("Throttled empty response after retries — giving up on %s", request.url)
        return response
