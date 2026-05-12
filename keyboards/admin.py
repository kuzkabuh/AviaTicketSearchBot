"""Inline-клавиатуры административного раздела."""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура административной панели."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📌 Версия бота", callback_data="admin:version")
    builder.button(text="🔍 Проверить обновления", callback_data="admin:check_updates")
    builder.button(text="⬆️ Обновить бота", callback_data="admin:update")
    builder.button(text="📋 Последний лог обновления", callback_data="admin:update_log")
    builder.button(text="◀️ В главное меню", callback_data="admin:main_menu")
    builder.adjust(1)
    return builder.as_markup()


def update_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения запуска обновления."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, обновить", callback_data="admin:update_confirm")
    builder.button(text="❌ Отмена", callback_data="admin:update_cancel")
    builder.adjust(1)
    return builder.as_markup()
