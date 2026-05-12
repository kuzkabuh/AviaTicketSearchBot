"""Точка входа AviaTicketSearchBot на aiogram 3.x."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from api import close_api_session
from config import settings
import db
from handlers import admin, search, start, subscriptions
from services.price_tracking import PriceTrackingService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Инициализирует Bot/Dispatcher, БД, Router-ы, price tracking и polling."""
    settings.validate()
    await db.init_db()

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    price_tracking = PriceTrackingService(bot)

    dispatcher.include_router(admin.router)
    dispatcher.include_router(start.router)
    dispatcher.include_router(search.router)
    dispatcher.include_router(subscriptions.router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await admin.notify_update_result_on_start(bot)
        price_tracking.start()
        logger.info("Bot polling started")
        await dispatcher.start_polling(bot)
    finally:
        await price_tracking.stop()
        await close_api_session()
        await bot.session.close()
        logger.info("Bot polling stopped")


if __name__ == "__main__":
    asyncio.run(main())
