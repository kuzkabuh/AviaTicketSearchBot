"""Inline-клавиатуры, построенные через InlineKeyboardBuilder aiogram 3.x."""

from typing import Any

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def popular_directions_keyboard(origin: str, directions: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Создает кнопки популярных направлений.

    В callback_data сохраняются только короткие IATA-коды, чтобы не превысить
    лимит Telegram на размер callback_data. Остальные детали билета уже показаны
    в тексте кнопки и будут заново запрошены после ввода даты.
    """
    builder = InlineKeyboardBuilder()

    for direction in directions:
        destination = direction.get("destination")
        if not destination:
            continue

        price = direction.get("price") or "—"
        airline = direction.get("airline") or "—"
        builder.button(
            text=f"{destination} · от {price} RUB · {airline}",
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
