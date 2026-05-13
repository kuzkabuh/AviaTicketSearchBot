"""Regex-based route extraction for airline news."""

from __future__ import annotations

import logging
import re

from app.news.models import RouteMatch
from services.autocomplete import autocomplete_locations

logger = logging.getLogger(__name__)

RU_ROUTE_RE = re.compile(r"(?:из|между)\s+(?P<origin>[А-ЯЁA-Z][А-ЯЁа-яёA-Za-z\-\s]+?)\s+(?:в|и)\s+(?P<destination>[А-ЯЁA-Z][А-ЯЁа-яёA-Za-z\-\s]+?)(?:[,.!;:]|$)")
EN_BETWEEN_RE = re.compile(r"between\s+(?P<origin>[A-Z][A-Za-z\-\s]+?)\s+and\s+(?P<destination>[A-Z][A-Za-z\-\s]+?)(?:[,.!;:]|$)", re.I)
EN_TO_RE = re.compile(r"(?:from\s+(?P<origin>[A-Z][A-Za-z\-\s]+?)\s+)?to\s+(?P<destination>[A-Z][A-Za-z\-\s]+?)(?:[,.!;:]|$)", re.I)


def extract_route_names(text: str | None) -> RouteMatch:
    value = text or ""
    for pattern in (RU_ROUTE_RE, EN_BETWEEN_RE, EN_TO_RE):
        match = pattern.search(value)
        if match:
            groups = match.groupdict()
            return RouteMatch(
                origin_name=(groups.get("origin") or "").strip() or None,
                destination_name=(groups.get("destination") or "").strip() or None,
                confidence=0.65,
            )
    return RouteMatch()


async def resolve_route_iata(route: RouteMatch, language_code: str = "ru") -> RouteMatch:
    """Validate extracted city names through Aviasales autocomplete API."""
    async def resolve(name: str | None) -> str | None:
        if not name:
            return None
        try:
            matches = await autocomplete_locations(name, locale=language_code)
        except Exception:  # noqa: BLE001
            logger.exception("Route autocomplete failed for %s", name)
            return None
        return matches[0].code if len(matches) == 1 else None

    return RouteMatch(
        origin_name=route.origin_name,
        destination_name=route.destination_name,
        origin_iata=await resolve(route.origin_name),
        destination_iata=await resolve(route.destination_name),
        confidence=route.confidence,
    )
