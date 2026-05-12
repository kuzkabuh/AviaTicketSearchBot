"""Служебные действия управления ботом из административной панели."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot

from config import settings
import db
from services.subscriptions import check_subscription_price


@dataclass(frozen=True)
class CleanupResult:
    deleted_files: int
    deleted_locks: int
    details: list[str]


@dataclass(frozen=True)
class ForceCheckResult:
    checked: int
    changed: int
    not_found: int
    errors: int


async def restart_bot_service() -> tuple[bool, str]:
    """Запускает безопасный systemd-рестарт настроенного сервиса."""
    if not settings.bot_restart_enabled:
        return False, "Рестарт отключён настройкой BOT_RESTART_ENABLED."
    process = await asyncio.create_subprocess_exec(
        "systemctl",
        "restart",
        settings.bot_service_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    output = (stderr or stdout).decode("utf-8", errors="replace").strip()
    return process.returncode == 0, output or "Команда рестарта выполнена."


async def cleanup_temp_files() -> CleanupResult:
    """Удаляет только заранее разрешённые временные файлы из runtime-директории."""
    if not settings.admin_temp_cleanup_enabled:
        return CleanupResult(0, 0, ["Очистка отключена настройкой ADMIN_TEMP_CLEANUP_ENABLED."])

    runtime_dir = Path(settings.bot_runtime_dir)
    allowed_suffixes = {".tmp", ".temp", ".json.tmp"}
    allowed_names = {"restart_notice.json"}
    deleted_files = 0
    deleted_locks = 0
    details: list[str] = []

    def _cleanup() -> CleanupResult:
        nonlocal deleted_files, deleted_locks
        if not runtime_dir.exists():
            return CleanupResult(0, 0, [f"Runtime-директория не найдена: {runtime_dir}"])
        for path in runtime_dir.iterdir():
            if not path.is_file():
                continue
            if path.name == Path(settings.bot_update_lock_path).name:
                continue
            is_lock = path.suffix == ".lock"
            is_temp = path.suffix in allowed_suffixes or path.name in allowed_names or path.name.endswith(".json.tmp")
            if not (is_lock or is_temp):
                continue
            try:
                path.unlink()
            except OSError as error:
                details.append(f"Не удалось удалить {path.name}: {error}")
                continue
            if is_lock:
                deleted_locks += 1
            else:
                deleted_files += 1
            details.append(f"Удалён файл: {path.name}")
        return CleanupResult(deleted_files, deleted_locks, details or ["Подходящих временных файлов не найдено."])

    return await asyncio.to_thread(_cleanup)


async def force_check_all_subscriptions(bot: Bot) -> ForceCheckResult:
    """Выполняет внеплановую проверку всех активных подписок."""
    if not settings.admin_force_subscriptions_check_enabled:
        return ForceCheckResult(0, 0, 0, 1)
    subscriptions = await db.list_active_subscriptions()
    checked = changed = not_found = errors = 0
    for subscription in subscriptions:
        try:
            result = await check_subscription_price(subscription, bot=bot, notify=True)
            checked += 1
            if result.get("status") == "changed":
                changed += 1
            elif result.get("status") == "not_found":
                not_found += 1
        except Exception:  # noqa: BLE001 - админская пакетная проверка продолжает обработку
            errors += 1
    await db.record_bot_event(None, "force_subscription_check", f"checked={checked};changed={changed};not_found={not_found};errors={errors}")
    return ForceCheckResult(checked, changed, not_found, errors)
