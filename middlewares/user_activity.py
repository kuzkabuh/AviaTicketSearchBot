"""Middleware для учета пользователей и последней активности."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

import db


class UserActivityMiddleware(BaseMiddleware):
    """Сохраняет профиль Telegram-пользователя при каждом сообщении/callback."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        if user:
            await db.upsert_user(user.id, user.username, user.first_name, user.last_name)
        return await handler(event, data)
