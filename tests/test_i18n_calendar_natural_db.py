from __future__ import annotations

import asyncio
from datetime import date
import sqlite3

import db
from services.calendar_keyboard import can_select_date
from services.i18n import defaults_for_language, translate
from services.natural_search_parser import parse_natural_search
from utils.formatters import format_money


def test_language_and_currency_defaults() -> None:
    assert translate("en", "menu.search") == "🔎 Search flights"
    assert translate("xx", "menu.search") == "🔎 Найти билет"
    assert defaults_for_language("ru") == ("RUB", "ru")
    assert defaults_for_language("en") == ("USD", "us")
    assert format_money(12500, "RUB") == "12 500 ₽"
    assert format_money(125, "USD") == "$125"
    assert format_money(119, "EUR") == "€119"


def test_calendar_date_guards() -> None:
    today = date(2026, 5, 13)
    assert not can_select_date(date(2026, 5, 12), today=today)
    assert can_select_date(date(2026, 5, 15), today=today)
    assert not can_select_date(date(2026, 5, 20), today=today, min_date=date(2026, 5, 21))
    assert can_select_date(date(2026, 5, 22), today=today, min_date=date(2026, 5, 21))


def test_parse_russian_round_trip_passengers() -> None:
    result = parse_natural_search(
        "Найди мне билеты из Москвы в Казань с 15 мая по 26 мая для 2 взрослых и 1 ребенка",
        today=date(2026, 5, 13),
    )
    assert result.origin_text == "Москвы"
    assert result.destination_text == "Казань"
    assert result.departure_date == "2026-05-15"
    assert result.return_date == "2026-05-26"
    assert result.trip_type == "round_trip"
    assert result.passengers.adults == 2
    assert result.passengers.children == 1


def test_parse_english_one_way() -> None:
    result = parse_natural_search("Find flights from Amsterdam to London on July 15 for 1 adult", today=date(2026, 5, 13))
    assert result.origin_text == "Amsterdam"
    assert result.destination_text == "London"
    assert result.departure_date == "2026-07-15"
    assert result.return_date is None
    assert result.trip_type == "one_way"
    assert result.passengers.adults == 1


def test_incomplete_query_reports_missing_origin() -> None:
    result = parse_natural_search("Найди билеты в Казань на 15 мая", today=date(2026, 5, 13))
    assert "origin" in result.missing
    assert result.departure_date == "2026-05-15"


def test_db_migration_is_idempotent(tmp_path, monkeypatch) -> None:
    database = tmp_path / "bot.sqlite3"
    original = db.settings.database_path
    object.__setattr__(db.settings, "database_path", str(database))
    try:
        asyncio.run(db.init_db())
        asyncio.run(db.init_db())
    finally:
        object.__setattr__(db.settings, "database_path", original)
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
    assert {"language_code", "currency_code", "market_code"} <= columns
