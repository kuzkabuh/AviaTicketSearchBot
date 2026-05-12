"""Inline-клавиатуры, построенные через InlineKeyboardBuilder aiogram 3.x."""

from typing import Any

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def location_options_keyboard(field: str, options: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру выбора города/аэропорта при неоднозначном вводе.

    В callback_data хранится только тип поля и индекс варианта в FSMContext — это
    гарантирует, что мы не превысим лимит Telegram на длину callback_data.
    """
    builder = InlineKeyboardBuilder()

    for index, option in enumerate(options):
        title_parts = [option.get("city_name") or option.get("name") or option.get("code")]
        airport_name = option.get("airport_name")
        if airport_name and airport_name not in title_parts:
            title_parts.append(airport_name)
        title_parts.append(option.get("code") or "")
        builder.button(
            text=" · ".join(part for part in title_parts if part),
            callback_data=f"loc:{field}:{index}",
        )

    builder.adjust(1)
    return builder.as_markup()


def popular_directions_keyboard(origin: str, directions: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Создаёт кнопки популярных направлений.

    В callback_data сохраняются только короткие IATA-коды, чтобы не превысить
    лимит Telegram. Детали направления показаны в тексте кнопки.
    """
    builder = InlineKeyboardBuilder()

    for direction in directions:
        destination = direction.get("destination")
        if not destination:
            continue

        price = direction.get("price") or "—"
        currency = direction.get("currency") or "RUB"
        airline = direction.get("airline") or "—"
        builder.button(
            text=f"{destination} · от {price} {currency} · {airline}",
            callback_data=f"popular:{origin}:{destination}",
        )

    builder.adjust(1)
    return builder.as_markup()


def start_search_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура быстрого перехода к основным сценариям бота."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔎 Найти билет", callback_data="menu:search")
    builder.button(text="🔥 Популярные направления", callback_data="menu:popular")
    builder.adjust(1)
    return builder.as_markup()
