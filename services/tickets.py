"""Сервис поиска и сопоставления авиабилетов."""

from __future__ import annotations

from typing import Any

from api import search_cheap_tickets
from config import settings


async def search_ticket_offers(origin: str, destination: str, date: str) -> list[dict[str, Any]]:
    """Возвращает до настроенного лимита разных вариантов перелета."""
    return await search_cheap_tickets(origin, destination, date, limit=settings.ticket_results_limit)


def find_matching_offer(subscription: dict[str, Any], offers: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Находит тот же или максимально похожий рейс среди новых результатов."""
    if not offers:
        return None

    offer_id = subscription.get("offer_id")
    if offer_id:
        for offer in offers:
            if offer.get("offer_id") == offer_id:
                return offer

    def score(offer: dict[str, Any]) -> int:
        value = 0
        comparisons = {
            "airline": "airline",
            "flight_number": "flight_number",
            "departure_time": "departure_time",
            "arrival_time": "arrival_time",
            "transfers": "transfers",
        }
        for subscription_field, offer_field in comparisons.items():
            left = subscription.get(subscription_field)
            right = offer.get(offer_field)
            if left not in (None, "", "-") and left == right:
                value += 2
        if offer.get("date") == subscription.get("departure_date"):
            value += 1
        return value

    best = max(offers, key=score)
    return best if score(best) > 0 else offers[0]
