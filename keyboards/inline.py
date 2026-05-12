"""
============================================================
Файл: keyboards/inline.py
Версия: 2.0.0
Дата изменения: 12.05.2026
Описание:
    Inline клавиатуры проекта.
============================================================
"""

from typing import Dict
from typing import List

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def popular_directions_keyboard(
    origin: str,
    directions: List[Dict]
) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры популярных направлений.
    """

    builder = InlineKeyboardBuilder()

    for direction in directions:

        destination = direction.get("destination")
        price = direction.get("price")

        builder.button(
            text=f"{destination} — {price} RUB",
            callback_data=f"popular:{origin}:{destination}"
        )

    builder.adjust(1)

    return builder.as_markup()