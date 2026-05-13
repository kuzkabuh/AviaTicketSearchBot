"""Бизнес-логика подписок на изменение цены."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from aiogram import Bot

import db
from config import settings
from services.tickets import find_matching_offer, search_ticket_offers
from utils.formatters import format_price_change

logger = logging.getLogger(__name__)


def _price(value: Any) -> float | None:
    """Преобразует цену к float."""
    return float(value) if isinstance(value, (int, float)) else None


async def create_subscription(
    telegram_user_id: int,
    telegram_username: str | None,
    offer: dict[str, Any],
    passengers: int,
    notification_mode: str = "any_change",
) -> tuple[bool, dict[str, Any] | None]:
    """Создает подписку с защитой от дублей."""
    created, subscription = await db.create_subscription(telegram_user_id, telegram_username, offer, passengers, notification_mode)
    if created:
        logger.info("Subscription created user=%s subscription=%s", telegram_user_id, subscription["id"] if subscription else None)
    else:
        logger.info("Duplicate subscription attempt user=%s offer=%s", telegram_user_id, offer.get("offer_id"))
    return created, subscription


async def get_user_subscriptions(telegram_user_id: int) -> list[dict[str, Any]]:
    """Возвращает активные подписки пользователя."""
    return await db.list_active_subscriptions(telegram_user_id)


async def delete_subscription(subscription_id: int, telegram_user_id: int) -> bool:
    """Удаляет подписку пользователя мягким удалением."""
    deleted = await db.mark_subscription_deleted(subscription_id, telegram_user_id)
    logger.info("Subscription delete subscription=%s user=%s deleted=%s", subscription_id, telegram_user_id, deleted)
    return deleted


def _can_notify(subscription: dict[str, Any]) -> bool:
    """Проверяет cooldown между повторными уведомлениями по одной подписке."""
    last_notified_at = subscription.get("last_notified_at")
    if not last_notified_at:
        return True
    try:
        last_dt = datetime.fromisoformat(last_notified_at)
    except ValueError:
        return True
    return datetime.now(timezone.utc) - last_dt >= timedelta(minutes=settings.duplicate_notification_cooldown_minutes)


async def check_subscription_price(subscription: dict[str, Any], bot: Bot | None = None, notify: bool = False) -> dict[str, Any]:
    """Проверяет актуальную цену одной подписки и при необходимости уведомляет."""
    subscription_id = subscription["id"]
    now = db.utcnow_iso()
    try:
        offers = await search_ticket_offers(subscription["origin_code"], subscription["destination_code"], subscription["departure_date"])
    except Exception as error:
        await db.update_subscription(subscription_id, last_checked_at=now, failed_checks=int(subscription.get("failed_checks") or 0) + 1)
        await db.record_bot_event(subscription.get("telegram_user_id"), "price_check_error", f"subscription={subscription_id};error={error}")
        raise
    match = find_matching_offer(subscription, offers)

    if not match:
        failed_checks = int(subscription.get("failed_checks") or 0) + 1
        await db.update_subscription(subscription_id, last_checked_at=now, failed_checks=failed_checks)
        await db.record_bot_event(subscription.get("telegram_user_id"), "flight_not_found", f"subscription={subscription_id}")
        logger.warning("Tracked flight not found subscription=%s failed_checks=%s", subscription_id, failed_checks)
        return {"status": "not_found", "old_price": subscription.get("last_price"), "new_price": None}

    old_price = _price(subscription.get("last_price"))
    new_price = _price(match.get("price"))
    update_fields = {
        "last_checked_at": now,
        "failed_checks": 0,
        "purchase_link": match.get("link") or subscription.get("purchase_link"),
    }

    if new_price is None:
        await db.update_subscription(subscription_id, **update_fields)
        await db.record_bot_event(subscription.get("telegram_user_id"), "price_check_success", f"subscription={subscription_id};no_price")
        return {"status": "no_price", "old_price": old_price, "new_price": None}

    changed = old_price is not None and new_price != old_price
    if changed:
        update_fields["last_price"] = new_price
        if notify and bot is not None and _can_notify(subscription):
            try:
                message_subscription = {**subscription, "purchase_link": match.get("link") or subscription.get("purchase_link")}
                await bot.send_message(
                    subscription["telegram_user_id"],
                    format_price_change(message_subscription, old_price, new_price),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                update_fields["last_notified_at"] = now
                event_type = "price_notification_down" if new_price < old_price else "price_notification_up"
                await db.record_bot_event(subscription.get("telegram_user_id"), event_type, f"subscription={subscription_id};old={old_price};new={new_price}")
                logger.info("Price notification sent subscription=%s old=%s new=%s", subscription_id, old_price, new_price)
            except Exception as exc:  # noqa: BLE001 - уведомление не должно ронять фоновую проверку
                logger.exception("Failed to send price notification subscription=%s: %s", subscription_id, exc)

    await db.update_subscription(subscription_id, **update_fields)
    await db.record_bot_event(subscription.get("telegram_user_id"), "price_changed" if changed else "price_check_success", f"subscription={subscription_id}")
    return {
        "status": "changed" if changed else "unchanged",
        "old_price": old_price,
        "new_price": new_price,
        "offer": match,
    }


def should_send_not_found_notice(subscription: dict[str, Any], cooldown_hours: int) -> bool:
    """Проверяет, можно ли отправить уведомление о недоступном рейсе."""
    last_notice = subscription.get("not_found_notified_at")
    if not last_notice:
        return True
    try:
        last_dt = datetime.fromisoformat(last_notice)
    except ValueError:
        return True
    return datetime.now(timezone.utc) - last_dt >= timedelta(hours=cooldown_hours)
