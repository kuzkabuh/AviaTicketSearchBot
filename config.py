import os
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

# Токен телеграм-бота (получать у @BotFather)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Токен Travelpayouts (получать на travelpayouts.com)
TRAVEL_API_TOKEN = os.getenv("TRAVEL_API_TOKEN")

# Базовый URL для API поиска дешевых авиабилетов
API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"