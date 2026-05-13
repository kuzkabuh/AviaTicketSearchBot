"""Extension point for fragile airline-specific parsers.

The first module version keeps a generic registry hook: when a site needs custom
logic, add a BaseNewsFetcher subclass here and map it in SPECIFIC_FETCHERS.
"""

from __future__ import annotations

from app.news.fetchers.base import BaseNewsFetcher

SPECIFIC_FETCHERS: dict[str, type[BaseNewsFetcher]] = {}
