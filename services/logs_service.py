"""Сервис безопасного чтения логов бота для административной панели."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from config import settings

MAX_TELEGRAM_PRE_TEXT = 3400
MAX_LINE_LENGTH = 220


@dataclass(frozen=True)
class LogView:
    """Результат чтения и фильтрации логов."""

    title: str
    text: str
    is_empty: bool = False


LOG_FILTERS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "latest": ("🧾 <b>Последние записи в логе бота</b>", (), "Лог бота пуст."),
    "errors": ("❌ <b>Последние ошибки бота</b>", ("ERROR", "CRITICAL", "Traceback", "Exception"), "✅ За последнее время ошибок в логах не найдено."),
    "warnings": ("⚠️ <b>Последние предупреждения бота</b>", ("WARNING", "WARN"), "✅ За последнее время предупреждений в логах не найдено."),
    "subscriptions": (
        "🔔 <b>Логи подписок</b>",
        ("Subscription", "subscription", "подпис", "Price notification", "Tracked flight", "price check"),
        "✅ Событий по подпискам в логах не найдено.",
    ),
    "search": (
        "🔍 <b>Логи поиска билетов</b>",
        ("search", "Search", "ticket", "tickets", "билет", "маршрут", "API"),
        "✅ Событий поиска билетов в логах не найдено.",
    ),
}


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return [f"Файл лога не найден: {path}"]
    if not path.is_file():
        return [f"Путь лога не является файлом: {path}"]
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as error:
        return [f"Не удалось прочитать файл лога: {error}"]


def _trim_line(line: str) -> str:
    line = line.rstrip()
    if len(line) <= MAX_LINE_LENGTH:
        return line
    return f"{line[:MAX_LINE_LENGTH - 1]}…"


def _limit_text(lines: list[str], limit: int) -> str:
    selected = [_trim_line(line) for line in lines[-limit:]]
    text = "\n".join(selected)
    if len(text) <= MAX_TELEGRAM_PRE_TEXT:
        return text
    return f"…\n{text[-MAX_TELEGRAM_PRE_TEXT:]}"


async def get_log_view(kind: str) -> LogView:
    """Возвращает подготовленный фрагмент логов для указанного раздела."""
    title, keywords, empty_text = LOG_FILTERS.get(kind, LOG_FILTERS["latest"])
    path = Path(settings.bot_error_log_path if kind == "errors" and settings.bot_error_log_path else settings.bot_log_path)
    limit = settings.admin_log_lines_limit

    def _prepare() -> LogView:
        lines = _read_lines(path)
        if keywords and path.exists() and path.is_file():
            filtered = [line for line in lines if any(keyword.lower() in line.lower() for keyword in keywords)]
        else:
            filtered = lines
        if not filtered or (len(filtered) == 1 and filtered[0] == ""):
            return LogView(title=title, text=empty_text, is_empty=True)
        return LogView(title=title, text=_limit_text(filtered, limit), is_empty=False)

    return await asyncio.to_thread(_prepare)
