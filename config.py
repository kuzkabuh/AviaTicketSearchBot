"""
Конфигурация AviaTicketSearchBot.

Модуль отвечает только за чтение переменных окружения и хранение настроек.
Валидация обязательных секретов вынесена в метод ``validate()``, чтобы тесты,
линтеры и импорт отдельных модулей не падали без локального файла ``.env``.
"""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


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
    database_path: str = "avia_bot.sqlite3"
    ticket_results_limit: int = 5
    min_ticket_results: int = 5
    price_tracking_enabled: bool = True
    price_check_interval_minutes: int = 60
    subscription_not_found_notify_interval_hours: int = 24
    duplicate_notification_cooldown_minutes: int = 30
    admin_telegram_ids: tuple[int, ...] = ()
    bot_project_dir: str = str(Path(__file__).resolve().parent)
    bot_git_branch: str = "master"
    bot_service_name: str = "avia-ticket-bot.service"
    bot_update_script: str = str(Path(__file__).resolve().parent / "update.sh")
    bot_update_log_path: str = str(Path(__file__).resolve().parent / "logs" / "update.log")
    bot_update_lock_path: str = str(Path(__file__).resolve().parent / "runtime" / "update.lock")
    bot_update_status_path: str = str(Path(__file__).resolve().parent / "runtime" / "update_status.json")
    bot_update_command_timeout_seconds: int = 120
    bot_log_path: str = str(Path(__file__).resolve().parent / "logs" / "bot.log")
    bot_error_log_path: str = str(Path(__file__).resolve().parent / "logs" / "error.log")
    admin_log_lines_limit: int = 50
    bot_restart_enabled: bool = True
    admin_force_subscriptions_check_enabled: bool = True
    admin_temp_cleanup_enabled: bool = True
    bot_runtime_dir: str = str(Path(__file__).resolve().parent / "runtime")

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


def _get_int_env(*names: str, default: int) -> int:
    """Безопасно читает целочисленную настройку."""
    raw_value = _get_env(*names, default=str(default))
    try:
        return int(raw_value)
    except ValueError:
        return default


def _get_int_tuple_env(*names: str) -> tuple[int, ...]:
    """Читает список целых чисел через запятую из переменной окружения."""
    raw_value = _get_env(*names)
    values: list[int] = []
    for item in raw_value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(int(item))
        except ValueError:
            continue
    return tuple(values)


def _get_bool_env(*names: str, default: bool) -> bool:
    """Безопасно читает булеву настройку из .env."""
    raw_value = _get_env(*names, default="true" if default else "false").lower()
    return raw_value in {"1", "true", "yes", "y", "on", "да"}


settings = Settings(
    bot_token=_get_env("BOT_TOKEN", "TELEGRAM_TOKEN"),
    travelpayouts_token=_get_env("TRAVELPAYOUTS_TOKEN"),
    base_url=_get_env("TRAVELPAYOUTS_BASE_URL", default="https://api.travelpayouts.com").rstrip("/"),
    currency=_get_env("CURRENCY", default="rub").lower(),
    marker=_get_env("MARKER"),
    request_timeout=_get_int_env("REQUEST_TIMEOUT", default=15),
    database_path=_get_env("DATABASE_PATH", default="avia_bot.sqlite3"),
    ticket_results_limit=max(1, _get_int_env("TICKET_RESULTS_LIMIT", default=5)),
    min_ticket_results=max(1, _get_int_env("MIN_TICKET_RESULTS", default=5)),
    price_tracking_enabled=_get_bool_env("PRICE_TRACKING_ENABLED", default=True),
    price_check_interval_minutes=max(1, _get_int_env("PRICE_CHECK_INTERVAL_MINUTES", default=60)),
    subscription_not_found_notify_interval_hours=max(
        1,
        _get_int_env("SUBSCRIPTION_NOT_FOUND_NOTIFY_INTERVAL_HOURS", default=24),
    ),
    duplicate_notification_cooldown_minutes=max(
        1,
        _get_int_env("DUPLICATE_NOTIFICATION_COOLDOWN_MINUTES", default=30),
    ),
    admin_telegram_ids=_get_int_tuple_env("ADMIN_TELEGRAM_IDS"),
    bot_project_dir=_get_env("BOT_PROJECT_DIR", default=str(Path(__file__).resolve().parent)),
    bot_git_branch=_get_env("BOT_GIT_BRANCH", default="master"),
    bot_service_name=_get_env("BOT_SERVICE_NAME", default="avia-ticket-bot.service"),
    bot_update_script=_get_env(
        "BOT_UPDATE_SCRIPT",
        default=str(Path(__file__).resolve().parent / "update.sh"),
    ),
    bot_update_log_path=_get_env(
        "BOT_UPDATE_LOG_PATH",
        default=str(Path(__file__).resolve().parent / "logs" / "update.log"),
    ),
    bot_update_lock_path=_get_env(
        "BOT_UPDATE_LOCK_PATH",
        default=str(Path(__file__).resolve().parent / "runtime" / "update.lock"),
    ),
    bot_update_status_path=_get_env(
        "BOT_UPDATE_STATUS_PATH",
        default=str(Path(__file__).resolve().parent / "runtime" / "update_status.json"),
    ),
    bot_update_command_timeout_seconds=max(
        10,
        _get_int_env("BOT_UPDATE_COMMAND_TIMEOUT_SECONDS", default=120),
    ),
    bot_log_path=_get_env(
        "BOT_LOG_PATH",
        default=str(Path(__file__).resolve().parent / "logs" / "bot.log"),
    ),
    bot_error_log_path=_get_env(
        "BOT_ERROR_LOG_PATH",
        default=str(Path(__file__).resolve().parent / "logs" / "error.log"),
    ),
    admin_log_lines_limit=max(1, _get_int_env("ADMIN_LOG_LINES_LIMIT", default=50)),
    bot_restart_enabled=_get_bool_env("BOT_RESTART_ENABLED", default=True),
    admin_force_subscriptions_check_enabled=_get_bool_env("ADMIN_FORCE_SUBSCRIPTIONS_CHECK_ENABLED", default=True),
    admin_temp_cleanup_enabled=_get_bool_env("ADMIN_TEMP_CLEANUP_ENABLED", default=True),
    bot_runtime_dir=_get_env(
        "BOT_RUNTIME_DIR",
        default=str(Path(__file__).resolve().parent / "runtime"),
    ),
)

BOT_TOKEN = settings.bot_token
TRAVELPAYOUTS_TOKEN = settings.travelpayouts_token
