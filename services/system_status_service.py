"""Сбор технического состояния приложения и сервера для админ-панели."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import shutil
import time

from config import settings
import db
from services.version_service import get_version_info

STARTED_AT = time.time()


@dataclass(frozen=True)
class SystemStatus:
    service_status: str
    uptime: str
    version: str
    commit_hash: str
    database_status: str
    price_tracking_status: str
    price_check_interval: str
    log_level: str
    active_subscriptions: int
    update_lock_exists: bool
    disk_free: str
    ram_usage: str
    cpu_load: str


def _format_uptime(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days} дн. {hours} ч."
    if hours:
        return f"{hours} ч. {minutes} мин."
    return f"{minutes} мин."


async def _systemctl_status() -> str:
    try:
        process = await asyncio.create_subprocess_exec(
            "systemctl",
            "is-active",
            settings.bot_service_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
    except (OSError, TimeoutError):
        return "недоступен"
    output = (stdout or stderr).decode("utf-8", errors="replace").strip()
    return output or "неизвестно"


def _ram_usage() -> str:
    try:
        data = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
        values = {}
        for line in data:
            key, raw = line.split(":", 1)
            values[key] = int(raw.strip().split()[0])
        total = values.get("MemTotal", 0) / 1024 / 1024
        available = values.get("MemAvailable", 0) / 1024 / 1024
        used = total - available
        return f"{used:.1f} / {total:.1f} ГБ"
    except (OSError, ValueError, IndexError):
        return "недоступно"


def _cpu_load() -> str:
    try:
        return f"{Path('/proc/loadavg').read_text(encoding='utf-8').split()[0]}"
    except (OSError, IndexError):
        return "недоступно"


async def get_system_status() -> SystemStatus:
    """Возвращает состояние сервиса, БД и основных ресурсов."""
    version_info = await get_version_info()
    service_status, db_status, active_subscriptions = await asyncio.gather(
        _systemctl_status(),
        db.check_database_status(),
        db.count_active_subscriptions(),
    )
    usage = shutil.disk_usage(settings.bot_project_dir)
    return SystemStatus(
        service_status=service_status,
        uptime=_format_uptime(time.time() - STARTED_AT),
        version=version_info.version,
        commit_hash=version_info.commit_hash,
        database_status=db_status,
        price_tracking_status="включена" if settings.price_tracking_enabled else "выключена",
        price_check_interval=f"{settings.price_check_interval_minutes} мин.",
        log_level=settings.log_level,
        active_subscriptions=active_subscriptions,
        update_lock_exists=Path(settings.bot_update_lock_path).exists(),
        disk_free=f"{usage.free / 1024 / 1024 / 1024:.1f} ГБ",
        ram_usage=_ram_usage(),
        cpu_load=_cpu_load(),
    )
