"""Base fetcher contracts for airline news sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.news.models import FetchedNewsItem


class FetcherError(RuntimeError):
    """Raised when a source cannot be fetched or parsed."""


class BaseNewsFetcher(ABC):
    @abstractmethod
    async def fetch(self, source: dict) -> list[FetchedNewsItem]:
        """Fetch source and return normalized news items."""
