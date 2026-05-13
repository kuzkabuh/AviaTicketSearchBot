"""Travelpayouts/Aviasales airline reference synchronization."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from app.news.airline_registry import seed_initial_airlines_and_sources
from app.news.repository import AirlineRepository, connect, ensure_news_schema

logger = logging.getLogger(__name__)
AIRLINES_REFERENCE_URL = "https://api.travelpayouts.com/data/airlines.json"
RUSSIA_NAMES = {"russia", "russian federation", "россия", "ru"}


def is_russian_airline(country: str | None, country_code: str | None = None) -> bool:
    return (country_code or "").upper() == "RU" or (country or "").strip().lower() in RUSSIA_NAMES


def normalize_reference_item(item: dict[str, Any]) -> dict[str, Any]:
    code = item.get("code") or item.get("iata") or item.get("iata_code")
    country = item.get("country") or item.get("country_name")
    country_code = item.get("country_code") or ("RU" if is_russian_airline(country) else None)
    name = item.get("name") or item.get("name_translations", {}).get("en") or code or "Unknown airline"
    return {
        "airline_code": code,
        "icao_code": item.get("icao_code") or item.get("icao"),
        "official_name": name,
        "display_name_ru": item.get("name_translations", {}).get("ru") if isinstance(item.get("name_translations"), dict) else None,
        "display_name_en": item.get("name_translations", {}).get("en") if isinstance(item.get("name_translations"), dict) else name,
        "country_code": country_code,
        "country_name": country,
        "is_russian": is_russian_airline(country, country_code),
        "is_active": int(bool(item.get("is_active"))) if item.get("is_active") is not None else None,
        "source_origin": "aviasales_reference",
    }


class AirlineSyncService:
    def __init__(self, reference_url: str = AIRLINES_REFERENCE_URL) -> None:
        self.reference_url = reference_url

    async def fetch_reference(self) -> list[dict[str, Any]]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(self.reference_url, headers={"User-Agent": "AviaTicketSearchBot/1.0"}) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        if isinstance(payload, dict):
            payload = payload.get("data") or payload.get("airlines") or []
        if not isinstance(payload, list):
            raise ValueError("Unexpected airlines reference payload")
        return [item for item in payload if isinstance(item, dict)]

    async def sync(self, items: list[dict[str, Any]] | None = None, seed_if_empty: bool = True) -> dict[str, int]:
        reference = items if items is not None else await self.fetch_reference()

        def _sync() -> dict[str, int]:
            with connect() as connection:
                ensure_news_schema(connection)
                repo = AirlineRepository(connection)
                if seed_if_empty and connection.execute("SELECT COUNT(*) FROM airlines").fetchone()[0] == 0:
                    seed_initial_airlines_and_sources(connection)
                created = updated = russian = 0
                for raw in reference:
                    data = normalize_reference_item(raw)
                    _, was_created = repo.upsert_airline(data, preserve_manual_sources=True)
                    created += int(was_created)
                    updated += int(not was_created)
                    russian += int(bool(data["is_russian"]))
                connection.commit()
                logger.info("Airline sync finished loaded=%s created=%s updated=%s russian=%s", len(reference), created, updated, russian)
                return {"loaded": len(reference), "created": created, "updated": updated, "russian": russian}
        return await asyncio.to_thread(_sync)
