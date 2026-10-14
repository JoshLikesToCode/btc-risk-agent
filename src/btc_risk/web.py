"""Minimal, allowlisted web fetch for the intel agent and URL ingestion.

Fetched pages are untrusted data. Callers must never treat their text as instructions.
"""

from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

ALLOWED_DOMAINS = (
    "treasury.gov",
    "home.treasury.gov",
    "ofac.treasury.gov",
    "fincen.gov",
    "fatf-gafi.org",
    "justice.gov",
    "chainalysis.com",
    "elliptic.co",
    "trmlabs.com",
    "bis.org",
    "imf.org",
)
MAX_CHARS = 20_000


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header"}

    def __init__(self):
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def is_allowed(url: str, allowed: tuple[str, ...] = ALLOWED_DOMAINS) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme in ("http", "https") and any(
        host == d or host.endswith("." + d) for d in allowed
    )


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return "\n".join(parser.parts)


def fetch_text(url: str, allowed: tuple[str, ...] | None = ALLOWED_DOMAINS) -> str:
    if allowed is not None and not is_allowed(url, allowed):
        raise ValueError(f"domain not on the allowlist: {url}")
    response = httpx.get(
        url, timeout=30, follow_redirects=True, headers={"User-Agent": "btc-risk-agent"}
    )
    response.raise_for_status()
    # a redirect must not escape the allowlist
    if allowed is not None and not is_allowed(str(response.url), allowed):
        raise ValueError(f"redirected off the allowlist: {response.url}")
    content_type = response.headers.get("content-type", "")
    if "pdf" in content_type:
        raise ValueError("PDF URL: download it and ingest the file path instead")
    text = html_to_text(response.text) if "html" in content_type else response.text
    return text[:MAX_CHARS]
