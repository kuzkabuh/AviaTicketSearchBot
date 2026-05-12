import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from config import BOT_TOKEN
from commands import start, track, list_subscriptions, help_command, support

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    """Запуск бота."""
    
    # 1. Проверка наличия токена внутри функции
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не найден в конфигурации! Проверьте файл config.py или .env")
        return

    # 2. Создание бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # 3. Регистрация обработчиков команд
    dp.message.register(start, Command("start"))
    dp.message.register(track, Command("track"))
    dp.message.register(list_subscriptions, Command("list"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(support, Command("support"))
    
    logger.info("Бот инициализирован и готов к работе...")

    # 4. Запуск бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        # Запуск асинхронного цикла
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Процесс бота прерван пользователем.")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}")