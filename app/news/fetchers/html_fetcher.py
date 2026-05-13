"""Conservative HTML fetcher for official airline pages without RSS."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin
import logging
import re

import aiohttp

from app.news.fetchers.base import BaseNewsFetcher, FetcherError
from app.news.models import FetchedNewsItem

logger = logging.getLogger(__name__)

DATE_RE = re.compile(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b")


class _LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attrs_dict = dict(attrs)
            self._href = attrs_dict.get("href")
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            text = " ".join(" ".join(self._chunks).split())
            if len(text) >= 12:
                self.links.append((text, urljoin(self.base_url, self._href)))
            self._href = None
            self._chunks = []


def parse_html_items(html: str, source: dict, max_items: int = 20) -> list[FetchedNewsItem]:
    """Parse links from an HTML listing page into news candidates."""
    url = source["source_url"]
    parser = _LinkParser(url)
    parser.feed(html)
    seen: set[str] = set()
    items: list[FetchedNewsItem] = []
    source_host = url.split("/")[2] if "/" in url[8:] else url
    for title, link in parser.links:
        lowered = link.lower()
        if link in seen or any(skip in lowered for skip in ("javascript:", "mailto:", "#")):
            continue
        if source_host not in link or not any(marker in lowered for marker in ("news", "press", "akcii", "promo", "about", "media", "novosti")):
            continue
        seen.add(link)
        date_match = DATE_RE.search(title)
        items.append(FetchedNewsItem(title=title, link=link, published_at=date_match.group(0) if date_match else None, language_code=source.get("language_code")))
        if len(items) >= max_items:
            break
    return items


class HtmlNewsFetcher(BaseNewsFetcher):
    def __init__(self, timeout: int = 20, max_items: int = 20) -> None:
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_items = max_items

    async def _get(self, url: str) -> str:
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers={"User-Agent": "AviaTicketSearchBot/1.0"}) as response:
                    if response.status >= 400:
                        raise FetcherError(f"HTTP {response.status}")
                    return await response.text()
        except aiohttp.ClientError as error:
            raise FetcherError(str(error)) from error

    async def fetch(self, source: dict) -> list[FetchedNewsItem]:
        url = source["source_url"]
        html = await self._get(url)
        return parse_html_items(html, source, self.max_items)
