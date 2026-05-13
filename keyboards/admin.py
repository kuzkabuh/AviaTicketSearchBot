"""Inline-клавиатуры административного раздела."""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура административной панели."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📌 Версия бота", callback_data="admin:version")
    builder.button(text="🔍 Проверить обновления", callback_data="admin:check_updates")
    builder.button(text="⬆️ Обновить бота", callback_data="admin:update")
    builder.button(text="📋 Лог обновления", callback_data="admin:update_log")
    builder.button(text="🧾 Логи бота", callback_data="admin:logs")
    builder.button(text="📊 Статистика", callback_data="admin:stats")
    builder.button(text="📰 Новости", callback_data="admin:news")
    builder.button(text="👥 Пользователи", callback_data="admin:users")
    builder.button(text="🩺 Состояние системы", callback_data="admin:system")
    builder.button(text="🔄 Перезапустить бота", callback_data="admin:restart")
    builder.button(text="🧹 Очистить временные файлы", callback_data="admin:cleanup")
    builder.button(text="🔔 Проверить все подписки сейчас", callback_data="admin:force_check")
    builder.button(text="📣 Рассылка", callback_data="admin:broadcast")
    builder.button(text="📨 Тестовое уведомление", callback_data="admin:test_notify")
    builder.button(text="◀️ В главное меню", callback_data="admin:main_menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_logs_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора вида логов."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Последние логи", callback_data="admin:logs:latest")
    builder.button(text="❌ Ошибки", callback_data="admin:logs:errors")
    builder.button(text="⚠️ Предупреждения", callback_data="admin:logs:warnings")
    builder.button(text="🔔 Логи подписок", callback_data="admin:logs:subscriptions")
    builder.button(text="🔍 Логи поиска билетов", callback_data="admin:logs:search")
    builder.button(text="⬅️ Назад", callback_data="admin:back")
    builder.adjust(1)
    return builder.as_markup()


def admin_stats_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура аналитики и периодов статистики."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Сегодня", callback_data="admin:stats:today")
    builder.button(text="📆 7 дней", callback_data="admin:stats:7d")
    builder.button(text="🗓 30 дней", callback_data="admin:stats:30d")
    builder.button(text="📈 Всё время", callback_data="admin:stats:all")
    builder.button(text="✈️ Популярные направления", callback_data="admin:stats:routes")
    builder.button(text="🔔 Аналитика подписок", callback_data="admin:stats:subscriptions")
    builder.button(text="⬅️ Назад", callback_data="admin:back")
    builder.adjust(2, 2, 1, 1, 1)
    return builder.as_markup()


def admin_users_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура раздела пользователей."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Последние пользователи", callback_data="admin:users:latest")
    builder.button(text="🔔 Пользователи с подписками", callback_data="admin:users:subscriptions")
    builder.button(text="⬅️ Назад", callback_data="admin:back")
    builder.adjust(1)
    return builder.as_markup()


def update_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения запуска обновления."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, обновить", callback_data="admin:update_confirm")
    builder.button(text="❌ Отмена", callback_data="admin:update_cancel")
    builder.adjust(1)
    return builder.as_markup()


def admin_restart_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения рестарта сервиса."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Перезапустить", callback_data="admin:restart_confirm")
    builder.button(text="❌ Отмена", callback_data="admin:restart_cancel")
    builder.adjust(1)
    return builder.as_markup()


def admin_force_check_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения внеплановой проверки подписок."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Проверить", callback_data="admin:force_check_confirm")
    builder.button(text="❌ Отмена", callback_data="admin:force_check_cancel")
    builder.adjust(1)
    return builder.as_markup()


def admin_broadcast_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения массовой рассылки."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить всем", callback_data="admin:broadcast_confirm")
    builder.button(text="❌ Отмена", callback_data="admin:broadcast_cancel")
    builder.adjust(1)
    return builder.as_markup()


def admin_news_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админского раздела новостей."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⏳ На модерации", callback_data="admin:news:pending")
    builder.button(text="✅ Одобренные", callback_data="admin:news:approved")
    builder.button(text="🚫 Отклонённые", callback_data="admin:news:rejected")
    builder.button(text="📡 Источники", callback_data="admin:news:sources")
    builder.button(text="✈️ Авиакомпании", callback_data="admin:news:airlines")
    builder.button(text="🔄 Запустить сбор вручную", callback_data="admin:news:collect")
    builder.button(text="🔁 Синхронизировать авиакомпании Aviasales", callback_data="admin:news:sync_airlines")
    builder.button(text="📊 Статистика новостей", callback_data="admin:news:stats")
    builder.button(text="⬅️ Назад", callback_data="admin:back")
    builder.adjust(1)
    return builder.as_markup()

def admin_news_moderation_keyboard(news_id: int) -> InlineKeyboardMarkup:
    """Кнопки модерации новости."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить и опубликовать", callback_data=f"admin:news:publish:{news_id}")
    builder.button(text="❌ Отклонить", callback_data=f"admin:news:reject:{news_id}")
    builder.button(text="🔄 Повторить классификацию", callback_data=f"admin:news:reclassify:{news_id}")
    builder.button(text="⬅️ К новостям", callback_data="admin:news")
    builder.adjust(1)
    return builder.as_markup()
