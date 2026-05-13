"""Helpers to seed and summarize the local airline registry."""

from __future__ import annotations

import logging
import sqlite3

from app.news.repository import AirlineRepository, NewsSourceRepository
from app.news.sources_registry import SEED_AIRLINES, SEED_SOURCES

logger = logging.getLogger(__name__)


def seed_initial_airlines_and_sources(connection: sqlite3.Connection) -> dict[str, int]:
    """Seed expandable airline/source registry without overwriting manual settings."""
    airline_repo = AirlineRepository(connection)
    source_repo = NewsSourceRepository(connection)
    created_airlines = 0
    created_sources = 0
    for airline in SEED_AIRLINES:
        row, created = airline_repo.upsert_airline({**airline, "source_origin": "manual", "has_news_source": airline.get("news_source_status") == "configured"})
        created_airlines += int(created)
    for source in SEED_SOURCES:
        airline = airline_repo.get_by_iata(str(source["airline_code"]))
        if not airline:
            continue
        _, created = source_repo.upsert_source({
            "airline_id": airline["id"],
            "airline_code": airline.get("airline_code"),
            "airline_name": airline.get("display_name_ru") or airline.get("official_name"),
            "country_code": airline.get("country_code"),
            "check_interval_minutes": 180 if source.get("source_type") in {"rss", "atom"} else 360,
            **source,
        })
        airline_repo.update_news_source_status(int(airline["id"]), "configured", True)
        created_sources += int(created)
    logger.info("Seeded news registry: airlines_created=%s sources_created=%s", created_airlines, created_sources)
    return {"seed_airlines_total": len(SEED_AIRLINES), "created_airlines": created_airlines, "seed_sources_total": len(SEED_SOURCES), "created_sources": created_sources}
