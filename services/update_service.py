"""Сервис проверки и запуска обновления бота из Git-репозитория."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
import subprocess

from config import settings
from utils.update_state import mark_update_failed, mark_update_started, read_update_state

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UpdateCheckResult:
    """Результат проверки удаленной ветки Git."""

    has_updates: bool
    branch: str
    local_commit: str
    remote_commit: str
    commits_behind: int
    latest_message: str


class UpdateError(RuntimeError):
    """Ошибка проверки или запуска обновления."""


def _run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=settings.bot_project_dir,
        check=True,
        capture_output=True,
        text=True,
        timeout=settings.bot_update_command_timeout_seconds,
    )
    return completed.stdout.strip()


def _check_updates_sync() -> UpdateCheckResult:
    branch = settings.bot_git_branch or _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    _run_git(["fetch", "origin", branch])

    local_commit = _run_git(["rev-parse", "--short", "HEAD"])
    remote_commit = _run_git(["rev-parse", "--short", f"origin/{branch}"])
    commits_behind_raw = _run_git(["rev-list", "--count", f"HEAD..origin/{branch}"])
    commits_behind = int(commits_behind_raw or "0")
    latest_message = ""
    if commits_behind > 0:
        latest_message = _run_git(["log", "-1", "--pretty=%s", f"origin/{branch}"])

    return UpdateCheckResult(
        has_updates=commits_behind > 0,
        branch=branch,
        local_commit=local_commit,
        remote_commit=remote_commit,
        commits_behind=commits_behind,
        latest_message=latest_message,
    )


async def check_updates() -> UpdateCheckResult:
    """Безопасно проверяет, отстает ли локальная ветка от origin."""
    logger.info("Checking bot updates from GitHub repository")
    try:
        result = await asyncio.to_thread(_check_updates_sync)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        logger.exception("Update check failed")
        raise UpdateError(str(error)) from error

    logger.info(
        "Update check finished: has_updates=%s local=%s remote=%s behind=%s",
        result.has_updates,
        result.local_commit,
        result.remote_commit,
        result.commits_behind,
    )
    return result


def is_update_running_sync() -> bool:
    """Проверяет наличие активного lock-файла/каталога обновления."""
    return Path(settings.bot_update_lock_path).exists()


async def is_update_running() -> bool:
    """Асинхронно проверяет, выполняется ли обновление."""
    state = await read_update_state()
    if state.get("status") == "in_progress":
        return True
    return await asyncio.to_thread(is_update_running_sync)


async def start_update(telegram_id: int) -> None:
    """Запускает update.sh в отдельной сессии, чтобы процесс пережил рестарт бота."""
    if await is_update_running():
        raise UpdateError("update_already_running")

    script_path = Path(settings.bot_update_script)
    if not script_path.exists():
        raise UpdateError(f"Скрипт обновления не найден: {script_path}")

    await mark_update_started(telegram_id)
    logger.info("Starting bot update script: %s", script_path)
    try:
        subprocess.Popen(  # noqa: S603 - путь берется из доверенной конфигурации, shell не используется.
            [str(script_path)],
            cwd=settings.bot_project_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as error:
        await mark_update_failed(str(error))
        logger.exception("Failed to start update script")
        raise UpdateError(str(error)) from error
