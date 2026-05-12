"""Точка входа AviaTicketSearchBot на aiogram 3.x."""

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from api import close_api_session
from config import settings
import db
from handlers import admin, search, start, subscriptions
from middlewares import UserActivityMiddleware
from services.price_tracking import PriceTrackingService


Path(settings.bot_log_path).parent.mkdir(parents=True, exist_ok=True)
Path(settings.bot_error_log_path).parent.mkdir(parents=True, exist_ok=True)
_error_file_handler = logging.FileHandler(settings.bot_error_log_path, encoding="utf-8")
_error_file_handler.setLevel(logging.ERROR)
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(settings.bot_log_path, encoding="utf-8"),
        _error_file_handler,
    ],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Инициализирует Bot/Dispatcher, БД, Router-ы, price tracking и polling."""
    settings.validate()
    await db.init_db()

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.message.middleware(UserActivityMiddleware())
    dispatcher.callback_query.middleware(UserActivityMiddleware())
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
