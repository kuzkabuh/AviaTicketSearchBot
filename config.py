"""
Конфигурация AviaTicketSearchBot.

Модуль отвечает только за чтение переменных окружения и хранение настроек.
Валидация обязательных секретов вынесена в метод ``validate()``, чтобы тесты,
линтеры и импорт отдельных модулей не падали без локального файла ``.env``.
"""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


# Загружаем .env один раз при импорте конфигурации. Значения из реального
# окружения имеют приоритет, если они уже выставлены перед запуском процесса.
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Набор настроек, необходимых для запуска бота и запросов к API."""

    bot_token: str
    travelpayouts_token: str
    base_url: str = "https://api.travelpayouts.com"
    currency: str = "rub"
    marker: str = ""
    request_timeout: int = 15

    def validate(self) -> None:
        """Проверяет наличие обязательных переменных перед стартом приложения."""
        missing_variables: list[str] = []

        if not self.bot_token:
            missing_variables.append("BOT_TOKEN (или TELEGRAM_TOKEN)")
        if not self.travelpayouts_token:
            missing_variables.append("TRAVELPAYOUTS_TOKEN")

        if missing_variables:
            joined_names = ", ".join(missing_variables)
            raise ValueError(f"Не заданы обязательные переменные окружения: {joined_names}")


def _get_env(*names: str, default: str = "") -> str:
    """Возвращает первое непустое значение из списка допустимых имен."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return default


settings = Settings(
    # Поддерживаем современное имя BOT_TOKEN и старое TELEGRAM_TOKEN из README,
    # чтобы миграция на aiogram не ломала существующие деплои пользователей.
    bot_token=_get_env("BOT_TOKEN", "TELEGRAM_TOKEN"),
    travelpayouts_token=_get_env("TRAVELPAYOUTS_TOKEN"),
    base_url=_get_env("TRAVELPAYOUTS_BASE_URL", default="https://api.travelpayouts.com").rstrip("/"),
    currency=_get_env("CURRENCY", default="rub").lower(),
    marker=_get_env("MARKER"),
    request_timeout=int(_get_env("REQUEST_TIMEOUT", default="15")),
)

# Совместимость с кодом/деплоями, которые импортировали константы напрямую.
BOT_TOKEN = settings.bot_token
TRAVELPAYOUTS_TOKEN = settings.travelpayouts_token
