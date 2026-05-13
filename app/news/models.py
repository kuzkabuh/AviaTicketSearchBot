"""Domain models for airline news, sources and subscriptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

NEWS_CATEGORIES = {
    "discount_sale",
    "promo_code",
    "new_route",
    "route_resumed",
    "frequency_increase",
    "seasonal_schedule",
    "general_news",
}
NEWS_STATUSES = {"pending", "approved", "rejected", "published"}
SOURCE_TYPES = {"rss", "atom", "html"}
NEWS_SOURCE_STATUSES = {"unknown", "configured", "not_found", "requires_manual_setup", "broken"}


@dataclass(frozen=True)
class FetchedNewsItem:
    """Normalized item returned by RSS/Atom and HTML fetchers before persistence."""

    title: str
    link: str
    summary: str | None = None
    content: str | None = None
    published_at: str | None = None
    external_id: str | None = None
    image_url: str | None = None
    language_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "title_original": self.title,
            "summary_original": self.summary,
            "content_original": self.content,
            "source_url": self.link,
            "published_at": self.published_at,
            "external_id": self.external_id,
            "image_url": self.image_url,
        }


@dataclass(frozen=True)
class ClassificationResult:
    category: str
    confidence: float
    matched_keywords: list[str]


@dataclass(frozen=True)
class RouteMatch:
    origin_name: str | None = None
    destination_name: str | None = None
    origin_iata: str | None = None
    destination_iata: str | None = None
    confidence: float = 0.0
