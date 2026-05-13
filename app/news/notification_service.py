"""Subscription matching and instant notification helpers."""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot

from app.news.formatters import format_news_card
from app.news.repository import NewsSubscriptionRepository, connect, ensure_news_schema
import db

logger = logging.getLogger(__name__)


def subscription_matches(news: dict[str, Any], subscription: dict[str, Any], is_russian: bool = False) -> bool:
    typ = subscription.get("subscription_type")
    if typ == "all":
        return True
    if typ == "all_russian_airlines":
        return is_russian
    if typ == "category":
        return subscription.get("category") == news.get("category")
    if typ == "airline":
        return (subscription.get("airline_id") and subscription.get("airline_id") == news.get("airline_id")) or (subscription.get("airline_code") and subscription.get("airline_code") == news.get("airline_code"))
    if typ == "personalized":
        return False
    return False


class NewsNotificationService:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def send_instant_for_news(self, news: dict[str, Any]) -> int:
        sent = 0
        with connect() as connection:
            ensure_news_schema(connection)
            users = connection.execute("SELECT DISTINCT user_id FROM user_news_subscriptions WHERE is_active = 1 AND notification_mode = 'instant'").fetchall()
            repo = NewsSubscriptionRepository(connection)
            airline = connection.execute("SELECT is_russian FROM airlines WHERE id = ?", (news.get("airline_id"),)).fetchone()
            is_russian = bool(airline and airline[0])
            for user in users:
                user_id = int(user[0])
                subscriptions = repo.list_user_subscriptions(user_id)
                if not any(subscription_matches(news, sub, is_russian) for sub in subscriptions):
                    continue
                if not repo.record_delivery(user_id, int(news["id"]), "instant"):
                    continue
                profile = await db.get_user_profile(user_id)
                language = (profile or {}).get("language_code") or "ru"
                try:
                    await self.bot.send_message(user_id, format_news_card(news, language), parse_mode="HTML", disable_web_page_preview=True)
                    sent += 1
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to send news notification user=%s news=%s", user_id, news.get("id"))
            connection.commit()
        return sent
