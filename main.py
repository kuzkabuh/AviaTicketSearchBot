import asyncio
import logging
from aiogram import Bot, Dispatcher, executor
from config import BOT_TOKEN
from handlers import send_welcome, search_handler

# Настройка логирования для отслеживания ошибок в консоли
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Регистрация обработчиков
dp.register_message_handler(send_welcome, commands=['start', 'help'])
dp.register_message_handler(search_handler) # Все остальные сообщения считаем поиском

if __name__ == '__main__':
    # Запуск бота в режиме long polling
    print("Бот запущен...")
    executor.start_polling(dp, skip_updates=True)