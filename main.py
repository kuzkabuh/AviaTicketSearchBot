import logging
import asyncio
from telegram.ext import Application
from config import BOT_TOKEN
from commands import get_handlers

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
        return # Теперь return находится внутри функции, что допустимо

    # 2. Создание приложения
    # Используем современный метод run_polling для упрощения жизненного цикла
    application = Application.builder().token(BOT_TOKEN).build()
    
    # 3. Регистрация обработчиков
    # Получаем список хендлеров из файла commands.py
    handlers = get_handlers()
    for handler in handlers:
        application.add_handler(handler)
    
    logger.info("Бот инициализирован и готов к работе...")

    # 4. Запуск бота
    # Метод run_polling автоматически обрабатывает старт, стоп и ожидание сигналов (Ctrl+C)
    await application.run_polling()

if __name__ == '__main__':
    try:
        # Запуск асинхронного цикла
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Процесс бота прерван пользователем.")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}")