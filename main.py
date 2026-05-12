"""Точка входа AviaTicketSearchBot на aiogram 3.x."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from api import close_api_session
from config import settings
from handlers import search, start


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Инициализирует Bot/Dispatcher, подключает Router-ы и запускает polling.

    MemoryStorage подходит для простого запуска и демонстрации FSM. В production
    его можно заменить на RedisStorage без изменения хендлеров.
    """
    settings.validate()

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher(storage=MemoryStorage())

    # Роутер стартовых команд подключается первым, затем сценарии поиска.
    dispatcher.include_router(start.router)
    dispatcher.include_router(search.router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Bot polling started")
        await dispatcher.start_polling(bot)
    finally:
        # Закрываем aiohttp-сессию API-клиента и HTTP-сессию Telegram Bot API.
        await close_api_session()
        await bot.session.close()
        logger.info("Bot polling stopped")


if __name__ == "__main__":
    asyncio.run(main())
