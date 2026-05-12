"""Хранение состояния серверного обновления между перезапусками бота."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from config import settings


def utcnow_iso() -> str:
    """Возвращает текущий UTC timestamp в ISO-формате."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _status_path() -> Path:
    return Path(settings.bot_update_status_path)


def _read_state_sync() -> dict[str, Any]:
    path = _status_path()
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state_sync(state: dict[str, Any]) -> None:
    path = _status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


async def read_update_state() -> dict[str, Any]:
    """Читает состояние обновления из JSON-файла."""
    return await asyncio.to_thread(_read_state_sync)


async def write_update_state(state: dict[str, Any]) -> None:
    """Записывает состояние обновления в JSON-файл."""
    await asyncio.to_thread(_write_state_sync, state)


async def mark_update_started(telegram_id: int) -> None:
    """Фиксирует запуск обновления администратором."""
    await write_update_state(
        {
            "telegram_id": telegram_id,
            "started_at": utcnow_iso(),
            "status": "in_progress",
            "notified": False,
        }
    )


async def mark_update_notified() -> None:
    """Помечает результат обновления доставленным администратору."""
    state = await read_update_state()
    if not state:
        return
    state["notified"] = True
    state["notified_at"] = utcnow_iso()
    await write_update_state(state)


async def mark_update_failed(message: str) -> None:
    """Фиксирует ошибку запуска обновления до старта shell-скрипта."""
    state = await read_update_state()
    state.update(
        {
            "status": "error",
            "message": message,
            "finished_at": utcnow_iso(),
            "notified": False,
        }
    )
    await write_update_state(state)
