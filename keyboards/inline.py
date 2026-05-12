"""Inline-клавиатуры, построенные через InlineKeyboardBuilder aiogram 3.x."""

from typing import Any

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.locations import Location


def popular_directions_keyboard(origin: str, directions: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    """Создает кнопки популярных направлений."""
    builder = InlineKeyboardBuilder()

    for direction in directions:
        destination = direction.get("destination")
        if not destination:
            continue

        price = direction.get("price") or "—"
        airline = direction.get("airline") or "—"
        builder.button(text=f"{destination} · от {price} RUB · {airline}", callback_data=f"popular:{origin}:{destination}")

    builder.adjust(1)
    return builder.as_markup()


def location_choice_keyboard(kind: str, locations: list[Location]) -> InlineKeyboardMarkup:
    """Кнопки выбора города/аэропорта при неоднозначном названии."""
    builder = InlineKeyboardBuilder()
    for location in locations:
        builder.button(text=location.display_name, callback_data=f"loc:{kind}:{location.code}")
    builder.adjust(1)
    return builder.as_markup()


def offer_subscribe_keyboard(token: str) -> InlineKeyboardMarkup:
    """Кнопка подписки на конкретный найденный вариант."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Отслеживать цену", callback_data=f"sub:create:{token}")
    return builder.as_markup()


def subscriptions_keyboard(subscriptions: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    """Кнопки управления активными подписками пользователя."""
    builder = InlineKeyboardBuilder()
    for subscription in subscriptions:
        subscription_id = subscription["id"]
        route = f"{subscription.get('origin_code')}→{subscription.get('destination_code')}"
        builder.button(text=f"🔄 Проверить цену сейчас · {route}", callback_data=f"sub:check:{subscription_id}")
        builder.button(text=f"❌ Удалить · {route}", callback_data=f"sub:delete:{subscription_id}")
    builder.adjust(1)
    return builder.as_markup()


def start_search_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура быстрого перехода к основным сценариям бота."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔎 Найти билет", callback_data="menu:search")
    builder.button(text="🔥 Популярные направления", callback_data="menu:popular")
    builder.button(text="🔔 Мои подписки", callback_data="menu:subscriptions")
    if is_admin:
        builder.button(text="⚙️ Админ-панель", callback_data="menu:admin")
    builder.adjust(1)
    return builder.as_markup()
