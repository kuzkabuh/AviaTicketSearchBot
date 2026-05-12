"""Проверка доступа к административному разделу бота."""

from __future__ import annotations

from config import settings


def is_admin(telegram_user_id: int | None) -> bool:
    """Возвращает True, если Telegram ID входит в список администраторов."""
    return telegram_user_id is not None and telegram_user_id in settings.admin_telegram_ids
