"""Экспорт inline-клавиатур приложения."""

from keyboards.admin import admin_panel_keyboard, update_confirmation_keyboard
from keyboards.inline import (
    location_choice_keyboard,
    offer_subscribe_keyboard,
    popular_directions_keyboard,
    start_search_keyboard,
    subscriptions_keyboard,
)

__all__ = [
    "admin_panel_keyboard",
    "update_confirmation_keyboard",
    "location_choice_keyboard",
    "offer_subscribe_keyboard",
    "popular_directions_keyboard",
    "start_search_keyboard",
    "subscriptions_keyboard",
]
