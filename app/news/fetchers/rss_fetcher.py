"""RSS/Atom fetcher based on aiohttp and stdlib XML parser."""

from __future__ import annotations

from email.utils import parsedate_to_datetime
import logging
import xml.etree.ElementTree as ET

import aiohttp

from app.news.fetchers.base import BaseNewsFetcher, FetcherError
from app.news.models import FetchedNewsItem

logger = logging.getLogger(__name__)


def _text(element: ET.Element | None, *paths: str) -> str | None:
    if element is None:
        return None
    for path in paths:
        found = element.find(path)
        if found is not None and found.text:
            return found.text.strip()
    return None


def _iso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError, IndexError):
        return value[:30]




def parse_feed(xml_text: str, source: dict) -> list[FetchedNewsItem]:
    """Parse RSS/Atom XML text into normalized items."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise FetcherError(f"Invalid XML: {error}") from error
    items: list[FetchedNewsItem] = []
    for item in root.findall(".//item"):
        title = _text(item, "title")
        link = _text(item, "link") or _text(item, "guid")
        if title and link:
            items.append(FetchedNewsItem(title=title, link=link, summary=_text(item, "description"), published_at=_iso_date(_text(item, "pubDate", "date")), external_id=_text(item, "guid"), language_code=source.get("language_code")))
    if not items:
        for entry in [el for el in root.iter() if el.tag.endswith("entry")]:
            title = next((child.text.strip() for child in entry if child.tag.endswith("title") and child.text), None)
            link = None
            for child in entry:
                if child.tag.endswith("link"):
                    link = child.attrib.get("href") or (child.text.strip() if child.text else None)
                    if link:
                        break
            external_id = next((child.text.strip() for child in entry if child.tag.endswith("id") and child.text), None)
            summary = next((child.text.strip() for child in entry if child.tag.endswith(("summary", "content")) and child.text), None)
            published = next((child.text.strip() for child in entry if child.tag.endswith(("published", "updated")) and child.text), None)
            if title and link:
                items.append(FetchedNewsItem(title=title, link=link, summary=summary, published_at=published, external_id=external_id, language_code=source.get("language_code")))
    return items
class RssNewsFetcher(BaseNewsFetcher):
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def fetch(self, source: dict) -> list[FetchedNewsItem]:
        url = source["source_url"]
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers={"User-Agent": "AviaTicketSearchBot/1.0"}) as response:
                    if response.status >= 400:
                        raise FetcherError(f"HTTP {response.status}")
                    xml_text = await response.text()
        except aiohttp.ClientError as error:
            raise FetcherError(str(error)) from error
        items = parse_feed(xml_text, source)
        if not items:
            logger.warning("RSS/Atom feed is empty or unsupported: %s", url)
        return items
