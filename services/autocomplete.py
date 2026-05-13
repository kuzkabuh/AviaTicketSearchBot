"""Aviasales Autocomplete API client with local fallback for city and airport lookup."""

from __future__ import annotations

from typing import Any

import aiohttp

from config import settings
from services.locations import Location, find_locations
from utils.validators import normalize_iata, validate_iata_format

AUTOCOMPLETE_ENDPOINT = "https://autocomplete.travelpayouts.com/places2"


def _normalize_type(value: str | None) -> str:
    if value in {"airport", "city"}:
        return value
    return "city"


def _location_from_payload(item: dict[str, Any]) -> Location | None:
    code = normalize_iata(str(item.get("code") or item.get("iata") or ""))
    if not validate_iata_format(code):
        return None
    name = str(item.get("name") or item.get("city_name") or code)
    city = str(item.get("city_name") or name)
    country = str(item.get("country_name") or "")
    kind = _normalize_type(str(item.get("type") or "city"))
    airport = name if kind == "airport" else "all airports"
    return Location(code=code, city=city, airport=airport, country=country, is_city=(kind == "city"))


async def autocomplete_locations(query: str | None, *, locale: str = "ru", limit: int = 8) -> list[Location]:
    """Resolve a query through Aviasales Autocomplete API and fall back to bundled locations."""
    raw_query = (query or "").strip()
    if not raw_query:
        return []
    normalized_code = normalize_iata(raw_query)
    if validate_iata_format(normalized_code):
        return find_locations(normalized_code, limit=limit)

    params = {"term": raw_query, "locale": locale if locale in {"ru", "en"} else "ru", "types[]": ["city", "airport"]}
    timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(AUTOCOMPLETE_ENDPOINT, params=params) as response:
                if response.status == 200:
                    payload = await response.json(content_type=None)
                    if isinstance(payload, list):
                        results = [location for item in payload if isinstance(item, dict) for location in [_location_from_payload(item)] if location]
                        if results:
                            unique: dict[str, Location] = {}
                            for location in results:
                                unique.setdefault(location.code, location)
                            return list(unique.values())[:limit]
    except (aiohttp.ClientError, TimeoutError, ValueError):
        pass
    return find_locations(raw_query, limit=limit)
