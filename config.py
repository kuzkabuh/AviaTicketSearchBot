import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла (если есть)
load_dotenv()

# Токен Telegram-бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Токен API Travelpayouts (Aviasales)
TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN")

# Проверяем, что оба токена заданы
if not BOT_TOKEN or not TRAVELPAYOUTS_TOKEN:
    raise ValueError("Не заданы переменные окружения BOT_TOKEN или TRAVELPAYOUTS_TOKEN")