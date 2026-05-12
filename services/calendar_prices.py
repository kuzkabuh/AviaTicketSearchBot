"""Сервис получения календарных цен вокруг выбранной даты."""

from __future__ import annotations

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


async def get_nearby_calendar_prices(origin: str, destination: str, departure_date: str, *, days: int = 3) -> list[dict[str, Any]]:
    """Возвращает минимальные найденные цены по датам в диапазоне ±days."""
    target_dates = _date_window(departure_date, days)
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
