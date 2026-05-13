"""Форматирование билетов, подписок и уведомлений для Telegram."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from services.airlines import format_airline_name


def format_money(value: Any, currency: str = "RUB") -> str:
    """Форматирует цену с валютой."""
    if not isinstance(value, (int, float)):
        return "—"
    number = f"{int(value):,}".replace(",", " ") if float(value).is_integer() else f"{value:,.2f}".replace(",", " ")
    code = currency.upper()
    if code in {"RUB", "RUR"}:
        return f"{number} ₽"
    if code == "USD":
        return f"${number}"
    if code == "EUR":
        return f"€{number}"
    return f"{number} {code}"


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


def format_passengers(adults: int = 1, children: int = 0, infants: int = 0, *, total: int | None = None) -> str:
    """Format passenger counters without zero categories."""
    if total is not None:
        adults = total
        children = 0
        infants = 0
    parts: list[str] = []
    if adults:
        parts.append(f"{adults} взрослых")
    if children:
        parts.append(f"{children} детей")
    if infants:
        parts.append(f"{infants} младенцев")
    return ", ".join(parts) or "1 взрослый"


def _date_label(value: Any) -> str:
    if not value:
        return "—"
    text = str(value)[:10]
    try:
        dt = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return str(value)
    months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    return f"{dt.day} {months[dt.month - 1]} {dt.year}"


def format_round_trip_no_results(origin: str, destination: str, departure_date: str, return_date: str | None, link: str) -> str:
    return (
        "В доступном кэше Aviasales не найдено корректных предложений туда-обратно на эти даты.\n\n"
        f"Маршрут: {escape(origin)} → {escape(destination)} → {escape(origin)}\n"
        f"Вылет: {escape(_date_label(departure_date))}\n"
        f"Возвращение: {escape(_date_label(return_date))}\n\n"
        "Можно проверить актуальные варианты по партнёрской ссылке Aviasales, попробовать соседние даты или выполнить поиск только «туда».\n"
        f'🔗 <a href="{escape(link, quote=True)}">Открыть поиск Aviasales туда-обратно</a>'
    )


def format_dt(value: str | None) -> str:
    """Форматирует ISO-даты для списка подписок."""
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value


def format_offer(
    offer: dict[str, Any],
    index: int,
    passengers: int,
    *,
    trip_type: str = "one_way",
    departure_date: str | None = None,
    return_date: str | None = None,
) -> str:
    """Форматирует найденный вариант перелета without overstating round-trip prices."""
    currency = offer.get("currency") or "RUB"
    price = offer.get("price")
    total = price * passengers if isinstance(price, (int, float)) else None
    link = offer.get("booking_link") or offer.get("link") or "https://www.aviasales.ru"
    is_round_trip = trip_type == "round_trip" and bool(offer.get("return_at"))
    if trip_type == "round_trip" and not is_round_trip:
        return format_round_trip_no_results(str(offer.get("origin") or "—"), str(offer.get("destination") or "—"), departure_date or str(offer.get("date") or ""), return_date, link)

    route = f"{offer.get('origin_city') or offer.get('origin')} → {offer.get('destination_city') or offer.get('destination')}"
    airline = format_airline_name(offer.get("airline_outbound") or offer.get("airline"))

    if is_round_trip:
        return_at = offer.get("return_at") or return_date
        return_time = str(return_at)[11:16] if isinstance(return_at, str) and "T" in return_at and len(return_at) >= 16 else "—"
        title = f"✈️ <b>Вариант {index} — туда и обратно</b>"
        lines = [
            title,
            "",
            f"<b>Маршрут:</b> {escape(route)} → {escape(str(offer.get('origin_city') or offer.get('origin') or '—'))}",
            "",
            "<b>Туда:</b>",
            f"• Дата и время: {escape(_date_label(departure_date or offer.get('departure_at') or offer.get('date')))} {escape(str(offer.get('departure_time') or '—'))}",
            f"• Из: {escape(str(offer.get('origin_airport') or '—'))} <code>{escape(str(offer.get('origin') or '—'))}</code>",
            f"• В: {escape(str(offer.get('destination_airport') or '—'))} <code>{escape(str(offer.get('destination') or '—'))}</code>",
            f"• Авиакомпания: {escape(airline)}",
            f"• Рейс: {escape(str(offer.get('flight_number_outbound') or offer.get('flight_number') or '-'))}",
            f"• Пересадки: {format_transfers(offer.get('transfers_outbound', offer.get('transfers')))}",
            "",
            "<b>Обратно:</b>",
            f"• Дата и время: {escape(_date_label(return_at))} {escape(return_time)}",
            f"• Из: <code>{escape(str(offer.get('destination') or '—'))}</code>",
            f"• В: <code>{escape(str(offer.get('origin') or '—'))}</code>",
            f"• Авиакомпания: {escape(format_airline_name(offer.get('airline_return')) if offer.get('airline_return') else 'API не предоставил отдельно')}",
            f"• Рейс: {escape(str(offer.get('flight_number_return') or 'API не предоставил отдельно'))}",
            f"• Пересадки: {format_transfers(offer.get('transfers_return'))}",
            "",
            f"<b>Общая длительность:</b> {format_duration(offer.get('duration'))}",
            f"<b>Длительность туда:</b> {format_duration(offer.get('duration_to'))}",
            f"<b>Длительность обратно:</b> {format_duration(offer.get('duration_back'))}",
            f"<b>Пассажиры:</b> {escape(format_passengers(total=passengers))}",
            f"<b>Цена найденного предложения туда-обратно из Data API:</b> {format_money(price, currency)}",
            "ℹ️ API предоставил агрегированные данные по предложению туда-обратно; невыданные поля не дополнялись искусственно.",
            "",
            f'🔗 <a href="{escape(link, quote=True)}">Купить билет</a>',
        ]
        return "\n".join(lines)

    return (
        f"✈️ <b>Вариант {index}</b>\n\n"
        f"<b>Маршрут:</b> {escape(route)}\n"
        f"<b>Вылет:</b> {escape(str(offer.get('origin_airport') or '—'))} <code>{escape(str(offer.get('origin') or '—'))}</code>\n"
        f"<b>Прилёт:</b> {escape(str(offer.get('destination_airport') or '—'))} <code>{escape(str(offer.get('destination') or '—'))}</code>\n"
        f"<b>Тип поездки:</b> В одну сторону\n"
        f"<b>Дата вылета:</b> {escape(_date_label(departure_date or offer.get('date')))}\n"
        f"<b>Время:</b> {escape(str(offer.get('departure_time') or '—'))} → {escape(str(offer.get('arrival_time') or '—'))}\n"
        f"<b>В пути:</b> {format_duration(offer.get('duration'))}\n"
        f"<b>Пересадки:</b> {format_transfers(offer.get('transfers'))}\n"
        f"<b>Авиакомпания:</b> {escape(airline)}\n"
        f"<b>Рейс:</b> {escape(str(offer.get('flight_number') or '-'))}\n"
        f"<b>Количество билетов:</b> {passengers}\n"
        f"<b>Цена за билет:</b> {format_money(price, currency)}\n"
        f"<b>Общая стоимость:</b> {format_money(total, currency)}\n\n"
        f'🔗 <a href="{escape(link, quote=True)}">Купить билет</a>'
    )


def format_notification_mode(value: str | None) -> str:
    """Форматирует режим уведомлений подписки."""
    labels = {
        "any_change": "при любом изменении",
        "price_drop": "только при снижении",
        "target_price": "ниже заданной суммы",
    }
    return labels.get(value or "any_change", "при любом изменении")


def format_subscription_list(subscriptions: list[dict[str, Any]]) -> str:
    """Форматирует список активных подписок пользователя."""
    if not subscriptions:
        return "У вас пока нет активных подписок на отслеживание цен."

    lines = ["🔔 <b>Ваши активные подписки</b>", ""]
    for index, subscription in enumerate(subscriptions, start=1):
        route = f"{subscription.get('origin_city')} → {subscription.get('destination_city')}"
        flight = ", ".join(filter(None, [subscription.get("airline"), subscription.get("flight_number")])) or "—"
        details = [
            f"<b>{index}. {escape(route)}</b>",
            f"📅 {escape(str(subscription.get('departure_date') or '—'))}",
            f"✈️ {escape(flight)}",
            f"🛫 Вылет: {escape(str(subscription.get('departure_time') or '—'))}",
            f"💰 Цена при подписке: {format_money(subscription.get('initial_price'), subscription.get('currency') or 'RUB')}",
            f"📌 Последняя цена: {format_money(subscription.get('last_price'), subscription.get('currency') or 'RUB')}",
            f"🔔 Режим уведомлений: {escape(format_notification_mode(subscription.get('notification_mode')))}",
        ]
        if subscription.get("target_price") is not None:
            details.append(f"🎯 Целевая цена: {format_money(subscription.get('target_price'), subscription.get('currency') or 'RUB')}")
        details.extend(
            [
                f"🕒 Проверено: {format_dt(subscription.get('last_checked_at'))}",
                f"📍 Статус: {escape(str(subscription.get('status') or '—'))}",
                "",
            ]
        )
        lines.extend(details)
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


def format_calendar_prices(
    prices: list[dict[str, Any]],
    *,
    origin: str,
    destination: str,
    departure_date: str,
    period_label: str,
    trip_type: str = "one_way",
    return_date: str | None = None,
    max_items: int | None = None,
    sort_by_price: bool = False,
) -> str:
    """Форматирует календарные цены для выбранного периода гибких дат."""
    trip_type_label = "Туда и обратно" if trip_type == "round_trip" else "В одну сторону"
    lowest_price = min(
        (item.get("price") for item in prices if isinstance(item.get("price"), (int, float))),
        default=None,
    )

    def sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
        date_value = str(item.get("date") or "")
        price = item.get("price")
        if sort_by_price:
            price_value = price if isinstance(price, (int, float)) else float("inf")
            return (price_value, date_value)
        return (date_value,)

    prepared_prices = sorted(prices, key=sort_key)
    total_count = len(prepared_prices)
    if max_items is not None:
        prepared_prices = prepared_prices[:max_items]

    lines = [
        f"📅 <b>Цены: {escape(period_label)}</b>",
        "",
        f"<b>Маршрут:</b> {escape(origin)} → {escape(destination)}",
        f"<b>Тип поездки:</b> {trip_type_label}",
        f"<b>Выбранная дата вылета:</b> {escape(departure_date)}",
    ]
    if trip_type == "round_trip" and return_date:
        lines.append(f"<b>Дата возвращения:</b> {escape(return_date)}")
    if max_items is not None and total_count > len(prepared_prices):
        lines.append(f"<b>Показано:</b> {len(prepared_prices)} самых дешёвых дат из {total_count}")
    lines.append("")

    for item in prepared_prices:
        price = item.get("price")
        currency = item.get("currency") or "RUB"
        date_value = str(item.get("date") or "—")
        markers = []
        if date_value == departure_date:
            markers.append("выбранная дата")
        if lowest_price is not None and price == lowest_price:
            markers.append("самая низкая цена")

        marker_text = f" — {'; '.join(markers)}" if markers else ""
        lines.append(f"• {escape(date_value)} — {format_money(price, currency)}{marker_text}")

    return "\n".join(lines)


def format_nearby_calendar_prices(
    prices: list[dict[str, Any]],
    *,
    origin: str,
    destination: str,
    departure_date: str,
    trip_type: str = "one_way",
    return_date: str | None = None,
) -> str:
    """Форматирует календарные цены для дат ±3 дня."""
    return format_calendar_prices(
        prices,
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        period_label="±3 дня",
        trip_type=trip_type,
        return_date=return_date,
    )
