"""Форматирование ответов пользователю."""

from __future__ import annotations

from html import escape
from typing import Any


def format_duration(minutes: int | None) -> str:
    """Преобразует длительность в минутах в вид '2 ч 35 мин'."""
    if minutes is None:
        return "не указана"

    hours, minutes_left = divmod(minutes, 60)
    if hours and minutes_left:
        return f"{hours} ч {minutes_left} мин"
    if hours:
        return f"{hours} ч"
    return f"{minutes_left} мин"


def format_transfers(transfers: int | None) -> str:
    """Возвращает понятное описание количества пересадок."""
    if transfers is None:
        return "не указано"
    if transfers == 0:
        return "без пересадок"
    if transfers == 1:
        return "1 пересадка"
    if 2 <= transfers <= 4:
        return f"{transfers} пересадки"
    return f"{transfers} пересадок"


def format_ticket_offer(offer: dict[str, Any], index: int, ticket_count: int) -> str:
    """Форматирует один вариант перелёта с детальной информацией."""
    origin = escape(str(offer.get("origin") or "—"))
    destination = escape(str(offer.get("destination") or "—"))
    origin_airport = escape(str(offer.get("origin_airport") or "—"))
    destination_airport = escape(str(offer.get("destination_airport") or "—"))
    departure_date = escape(str(offer.get("departure_date") or offer.get("date") or "—"))
    departure_time = escape(str(offer.get("departure_time") or "не указано"))
    arrival_time = escape(str(offer.get("arrival_time") or "не указано"))
    airline = escape(str(offer.get("airline") or "не указана"))
    flight_number = escape(str(offer.get("flight_number") or "-"))
    currency = escape(str(offer.get("currency") or "RUB"))
    price = offer.get("price") or "—"
    link = escape(str(offer.get("link") or "https://www.aviasales.ru"), quote=True)

    return (
        f"<b>{index}. Вариант перелёта</b>\n"
        f"🛫 Откуда: {origin}, аэропорт {origin_airport}\n"
        f"🛬 Куда: {destination}, аэропорт {destination_airport}\n"
        f"📅 Дата вылета: {departure_date}\n"
        f"⏰ Вылет: {departure_time}; прилёт: {arrival_time}\n"
        f"⏱ Длительность: {format_duration(offer.get('duration'))}\n"
        f"🔁 Пересадки: {format_transfers(offer.get('transfers'))}\n"
        f"✈️ Авиакомпания: {airline}\n"
        f"🔢 Рейс: {flight_number}\n"
        f"🎫 Количество билетов: {ticket_count}\n"
        f"💰 Стоимость: {price} {currency}\n"
        f"🔗 <a href=\"{link}\">Купить билет</a>"
    )


def format_ticket_offers(offers: list[dict[str, Any]], ticket_count: int) -> str:
    """Форматирует список вариантов перелёта для одного Telegram-сообщения."""
    formatted_offers = [
        format_ticket_offer(offer, index, ticket_count)
        for index, offer in enumerate(offers, start=1)
    ]
    return "✈️ <b>Найденные варианты:</b>\n\n" + "\n\n".join(formatted_offers)
