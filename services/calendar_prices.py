"""Сервис получения календарных цен вокруг выбранной даты."""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta
from typing import Any

from api import get_calendar_prices

DATE_FORMAT = "%Y-%m-%d"


def _parse_date(date_value: str) -> datetime.date:
    """Преобразует строку даты YYYY-MM-DD в date."""
    return datetime.strptime(date_value, DATE_FORMAT).date()


def _date_window(center_date: str, days: int) -> set[str]:
    """Возвращает множество дат в диапазоне ±days вокруг center_date."""
    center = _parse_date(center_date)
    return {(center + timedelta(days=offset)).isoformat() for offset in range(-days, days + 1)}


def _month_window(center_date: str) -> set[str]:
    """Возвращает множество дат календарного месяца выбранной даты."""
    center = _parse_date(center_date)
    _, days_in_month = monthrange(center.year, center.month)
    return {center.replace(day=day).isoformat() for day in range(1, days_in_month + 1)}


async def _get_calendar_prices_for_dates(origin: str, destination: str, target_dates: set[str]) -> list[dict[str, Any]]:
    """Возвращает минимальные найденные цены по переданному набору дат."""
    prices_by_date: dict[str, dict[str, Any]] = {}

    for flight_date in sorted(target_dates):
        offers = await get_calendar_prices(origin, destination, flight_date)
        for offer in offers:
            offer_date = str(offer.get("date") or flight_date)[:10]
            if offer_date not in target_dates:
                continue

            price = offer.get("price")
            if not isinstance(price, (int, float)):
                continue

            current = prices_by_date.get(offer_date)
            if current is None or price < current["price"]:
                prices_by_date[offer_date] = {
                    "date": offer_date,
                    "price": price,
                    "currency": offer.get("currency") or "RUB",
                }

    return [prices_by_date[date_value] for date_value in sorted(prices_by_date)]


async def get_nearby_calendar_prices(origin: str, destination: str, departure_date: str, *, days: int = 3) -> list[dict[str, Any]]:
    """Возвращает минимальные найденные цены по датам в диапазоне ±days."""
    return await _get_calendar_prices_for_dates(origin, destination, _date_window(departure_date, days))


async def get_week_calendar_prices(origin: str, destination: str, departure_date: str) -> list[dict[str, Any]]:
    """Возвращает минимальные найденные цены за неделю вокруг выбранной даты."""
    return await get_nearby_calendar_prices(origin, destination, departure_date, days=7)


async def get_month_calendar_prices(origin: str, destination: str, departure_date: str) -> list[dict[str, Any]]:
    """Возвращает минимальные найденные цены за календарный месяц выбранной даты."""
    return await _get_calendar_prices_for_dates(origin, destination, _month_window(departure_date))
