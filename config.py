"""
============================================================
Файл: config.py
Версия: 2.0.0
Дата изменения: 12.05.2026
Описание:
    Конфигурационный файл проекта.
    Загружает переменные окружения из .env.
============================================================
"""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


# Загружаем переменные окружения
load_dotenv()


@dataclass
class Settings:
    """
    Основной класс конфигурации приложения.
    """

    BOT_TOKEN: str
    TRAVELPAYOUTS_TOKEN: str
    BASE_URL: str = "https://api.travelpayouts.com"
    CURRENCY: str = "rub"


settings = Settings(
    BOT_TOKEN=os.getenv("BOT_TOKEN", ""),
    TRAVELPAYOUTS_TOKEN=os.getenv("TRAVELPAYOUTS_TOKEN", "")
)


# Проверка обязательных переменных
if not settings.BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN в .env")

if not settings.TRAVELPAYOUTS_TOKEN:
    raise ValueError("Не найден TRAVELPAYOUTS_TOKEN в .env")