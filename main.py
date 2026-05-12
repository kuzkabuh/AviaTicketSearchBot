import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from handlers import start, search

# Настройка логирования
logging.basicConfig(level=logging.INFO)

async def main():
    # Создаём экземпляр бота
    bot = Bot(token=BOT_TOKEN)
    # Хранилище состояний (можно использовать RedisStorage для production, но для примера MemoryStorage)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Подключаем роутеры из хендлеров
    dp.include_router(start.router)
    dp.include_router(search.router)

    # Удаляем вебхук (на случай, если он был установлен ранее)
    await bot.delete_webhook(drop_pending_updates=True)

    # Запускаем поллинг
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())