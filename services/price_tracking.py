"""Фоновая периодическая проверка цен по активным подпискам."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from config import settings
import db
from services.subscriptions import check_subscription_price, should_send_not_found_notice

logger = logging.getLogger(__name__)


class PriceTrackingService:
    """Запускает цикл проверки активных подписок вместе с ботом."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        """Стартует фоновый цикл, если он включен в настройках."""
        if not settings.price_tracking_enabled:
            logger.info("Price tracking disabled by PRICE_TRACKING_ENABLED")
            return
        self._task = asyncio.create_task(self._run(), name="price-tracking")
        logger.info("Price tracking started interval=%s minutes", settings.price_check_interval_minutes)

    async def stop(self) -> None:
        """Останавливает фоновый цикл."""
        self._stopping.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Price tracking stopped")

    async def _run(self) -> None:
        """Бесконечный цикл с защитой от падения на одной подписке."""
        while not self._stopping.is_set():
            await self.check_all_once()
            try:
                await asyncio.wait_for(
                    self._stopping.wait(),
                    timeout=settings.price_check_interval_minutes * 60,
                )
            except TimeoutError:
                continue

    async def check_all_once(self) -> None:
        """Один проход проверки всех активных подписок."""
        subscriptions = await db.list_active_subscriptions()
        logger.info("Automatic price check started subscriptions=%s", len(subscriptions))
        for subscription in subscriptions:
            try:
                result = await check_subscription_price(subscription, bot=self.bot, notify=True)
                if result["status"] == "not_found" and should_send_not_found_notice(
                    subscription,
                    settings.subscription_not_found_notify_interval_hours,
                ):
                    await self.bot.send_message(
                        subscription["telegram_user_id"],
                        "ℹ️ Не удалось найти отслеживаемый рейс по прежним параметрам.\n"
                        "Возможно, он временно недоступен или изменился в выдаче.",
                    )
                    await db.update_subscription(subscription["id"], not_found_notified_at=db.utcnow_iso())
            except Exception as exc:  # noqa: BLE001 - одна ошибка не должна останавливать сервис
                logger.exception("Automatic price check failed subscription=%s: %s", subscription.get("id"), exc)
