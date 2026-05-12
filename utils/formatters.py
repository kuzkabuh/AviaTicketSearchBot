"""Форматирование билетов, подписок и уведомлений для Telegram."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any


def format_money(value: Any, currency: str = "RUB") -> str:
    """Форматирует цену с валютой."""
    if not isinstance(value, (int, float)):
        return "—"
    number = f"{int(value):,}".replace(",", " ") if float(value).is_integer() else f"{value:,.2f}".replace(",", " ")
    sign = "₽" if currency.upper() in {"RUB", "RUR"} else currency.upper()
    return f"{number} {sign}"


def format_duration(minutes: Any) -> str:
    """Форматирует продолжительность из минут."""
    if not isinstance(minutes, int) or minutes <= 0:
        return "—"
    hours, mins = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} ч")
    if mins:
        parts.append(f"{mins} мин")
    return " ".join(parts) or "—"


def format_transfers(transfers: Any) -> str:
    """Форматирует количество пересадок."""
    if transfers is None:
        return "—"
    if transfers == 0:
        return "без пересадок"
    return f"{transfers} пересадк."


def format_dt(value: str | None) -> str:
    """Форматирует ISO-даты для списка подписок."""
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value


def format_offer(offer: dict[str, Any], index: int, passengers: int) -> str:
    """Форматирует найденный вариант перелета."""
    currency = offer.get("currency") or "RUB"
    price = offer.get("price")
    total = price * passengers if isinstance(price, (int, float)) else None
    link = offer.get("link") or "https://www.aviasales.ru"
    route = f"{offer.get('origin_city') or offer.get('origin')} → {offer.get('destination_city') or offer.get('destination')}"

    return (
        f"✈️ <b>Вариант {index}</b>\n\n"
        f"<b>Маршрут:</b> {escape(route)}\n"
        f"<b>Вылет:</b> {escape(str(offer.get('origin_airport') or '—'))} <code>{escape(str(offer.get('origin') or '—'))}</code>\n"
        f"<b>Прилёт:</b> {escape(str(offer.get('destination_airport') or '—'))} <code>{escape(str(offer.get('destination') or '—'))}</code>\n"
        f"<b>Дата:</b> {escape(str(offer.get('date') or '—'))}\n"
        f"<b>Время:</b> {escape(str(offer.get('departure_time') or '—'))} → {escape(str(offer.get('arrival_time') or '—'))}\n"
        f"<b>В пути:</b> {format_duration(offer.get('duration'))}\n"
        f"<b>Пересадки:</b> {format_transfers(offer.get('transfers'))}\n"
        f"<b>Авиакомпания:</b> {escape(str(offer.get('airline') or 'не указана'))}\n"
        f"<b>Рейс:</b> {escape(str(offer.get('flight_number') or '-'))}\n"
        f"<b>Количество билетов:</b> {passengers}\n"
        f"<b>Цена за билет:</b> {format_money(price, currency)}\n"
        f"<b>Общая стоимость:</b> {format_money(total, currency)}\n\n"
        f"🔗 <a href=\"{escape(link, quote=True)}\">Купить билет</a>"
    )


def format_subscription_list(subscriptions: list[dict[str, Any]]) -> str:
    """Форматирует список активных подписок пользователя."""
    if not subscriptions:
        return "У вас пока нет активных подписок на отслеживание цен."

    lines = ["🔔 <b>Ваши активные подписки</b>", ""]
    for index, subscription in enumerate(subscriptions, start=1):
        route = f"{subscription.get('origin_city')} → {subscription.get('destination_city')}"
        flight = ", ".join(filter(None, [subscription.get("airline"), subscription.get("flight_number")])) or "—"
        lines.extend(
            [
                f"<b>{index}. {escape(route)}</b>",
                f"📅 {escape(str(subscription.get('departure_date') or '—'))}",
                f"✈️ {escape(flight)}",
                f"🛫 Вылет: {escape(str(subscription.get('departure_time') or '—'))}",
                f"💰 Цена при подписке: {format_money(subscription.get('initial_price'), subscription.get('currency') or 'RUB')}",
                f"📌 Последняя цена: {format_money(subscription.get('last_price'), subscription.get('currency') or 'RUB')}",
                f"🕒 Проверено: {format_dt(subscription.get('last_checked_at'))}",
                f"📍 Статус: {escape(str(subscription.get('status') or '—'))}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def format_price_change(subscription: dict[str, Any], old_price: float, new_price: float) -> str:
    """Форматирует уведомление об изменении цены."""
    decreased = new_price < old_price
    delta = new_price - old_price
    currency = subscription.get("currency") or "RUB"
    title = "📉 <b>Цена на отслеживаемый рейс снизилась!</b>" if decreased else "📈 <b>Цена на отслеживаемый рейс изменилась!</b>"
    result_label = "✅ Стало" if decreased else "❗ Стало"
    delta_label = "🔻 Изменение" if decreased else "🔺 Изменение"
    route = f"{subscription.get('origin_city')} → {subscription.get('destination_city')}"
    flight = ", ".join(filter(None, [subscription.get("airline"), subscription.get("flight_number")])) or "—"
    link = subscription.get("purchase_link") or "https://www.aviasales.ru"
    sign_delta = f"{delta:+.0f}" if float(delta).is_integer() else f"{delta:+.2f}"

    return (
        f"{title}\n\n"
        f"✈️ {escape(route)}\n"
        f"📅 Дата: {escape(str(subscription.get('departure_date') or '—'))}\n"
        f"🛫 Вылет: {escape(str(subscription.get('departure_time') or '—'))}\n"
        f"🛬 Прилёт: {escape(str(subscription.get('arrival_time') or '—'))}\n"
        f"✈️ Авиакомпания: {escape(flight)}\n\n"
        f"💰 Было: {format_money(old_price, currency)}\n"
        f"{result_label}: {format_money(new_price, currency)}\n"
        f"{delta_label}: {escape(sign_delta)} {('₽' if currency.upper() in {'RUB', 'RUR'} else currency.upper())}\n\n"
        f"🔗 <a href=\"{escape(link, quote=True)}\">Открыть билет</a>"
    )
