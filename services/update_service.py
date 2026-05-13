"""Сервис проверки и запуска обновления бота из Git-репозитория."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import stat
import subprocess

from config import settings
from utils.update_state import mark_update_failed, mark_update_started, read_update_state

logger = logging.getLogger(__name__)
DUBIOUS_OWNERSHIP_MARKER = "detected dubious ownership"


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


def _project_dir() -> Path:
    return Path(settings.bot_project_dir).resolve()


def _format_git_error(error: subprocess.CalledProcessError) -> str:
    stderr = (error.stderr or "").strip()
    stdout = (error.stdout or "").strip()
    details = stderr or stdout or str(error)
    return details[-2000:]


def _add_safe_directory() -> None:
    project_dir = str(_project_dir())
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", project_dir],
        check=True,
        capture_output=True,
        text=True,
        timeout=settings.bot_update_command_timeout_seconds,
    )
    logger.warning("Added Git safe.directory for bot project: %s", project_dir)


def _run_git(args: list[str], *, retry_safe_directory: bool = True) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=_project_dir(),
            check=True,
            capture_output=True,
            text=True,
            timeout=settings.bot_update_command_timeout_seconds,
        )
    except subprocess.CalledProcessError as error:
        message = _format_git_error(error)
        if retry_safe_directory and DUBIOUS_OWNERSHIP_MARKER in message.lower():
            _add_safe_directory()
            return _run_git(args, retry_safe_directory=False)
        raise UpdateError(message) from error
    return completed.stdout.strip()


def _check_updates_sync() -> UpdateCheckResult:
    project_dir = _project_dir()
    if not project_dir.exists():
        raise UpdateError(f"Каталог проекта не найден: {project_dir}")
    if not (project_dir / ".git").exists():
        raise UpdateError(f"Каталог не является Git-репозиторием: {project_dir}")

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
    except (OSError, ValueError, subprocess.SubprocessError, UpdateError) as error:
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


def _script_command(script_path: Path) -> list[str]:
    """Возвращает команду запуска скрипта, даже если у файла нет executable bit."""
    try:
        mode = script_path.stat().st_mode
    except OSError:
        return ["bash", str(script_path)]
    if mode & stat.S_IXUSR:
        return [str(script_path)]
    return ["bash", str(script_path)]


def _update_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "BOT_PROJECT_DIR": str(_project_dir()),
            "BOT_GIT_BRANCH": settings.bot_git_branch,
            "BOT_SERVICE_NAME": settings.bot_service_name,
            "BOT_UPDATE_SCRIPT": settings.bot_update_script,
            "BOT_UPDATE_LOG_PATH": settings.bot_update_log_path,
            "BOT_UPDATE_LOCK_PATH": settings.bot_update_lock_path,
            "BOT_UPDATE_STATUS_PATH": settings.bot_update_status_path,
            "DATABASE_PATH": settings.database_path,
        }
    )
    return env


async def start_update(telegram_id: int) -> None:
    """Запускает update.sh в отдельной сессии, чтобы процесс пережил рестарт бота."""
    if await is_update_running():
        raise UpdateError("update_already_running")

    script_path = Path(settings.bot_update_script).resolve()
    if not script_path.exists() or not script_path.is_file():
        raise UpdateError(f"Скрипт обновления не найден: {script_path}")

    project_dir = _project_dir()
    if not project_dir.exists():
        raise UpdateError(f"Каталог проекта не найден: {project_dir}")

    await mark_update_started(telegram_id)
    logger.info("Starting bot update script: %s", script_path)
    try:
        subprocess.Popen(  # noqa: S603 - shell не используется, аргументы передаются списком.
            _script_command(script_path),
            cwd=project_dir,
            env=_update_environment(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as error:
        await mark_update_failed(str(error))
        logger.exception("Failed to start update script")
        raise UpdateError(str(error)) from error
