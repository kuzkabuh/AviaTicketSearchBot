"""Получение версии бота и информации о локальном Git-репозитории."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import subprocess

from config import settings


@dataclass(frozen=True)
class VersionInfo:
    """Сводка о версии приложения и текущем состоянии репозитория."""

    version: str
    branch: str
    project_dir: str
    commit_hash: str
    commit_date: str
    remote_url: str


def read_version() -> str:
    """Читает версию из файла VERSION в директории проекта."""
    version_file = Path(settings.bot_project_dir) / "VERSION"
    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "неизвестно"
    return version or "неизвестно"


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


def _safe_git(args: list[str], default: str = "неизвестно") -> str:
    try:
        return _run_git(args) or default
    except (OSError, subprocess.SubprocessError):
        return default


def get_version_info_sync() -> VersionInfo:
    """Синхронно собирает версию и Git-метаданные."""
    branch = _safe_git(["rev-parse", "--abbrev-ref", "HEAD"], settings.bot_git_branch)
    return VersionInfo(
        version=read_version(),
        branch=branch,
        project_dir=settings.bot_project_dir,
        commit_hash=_safe_git(["rev-parse", "--short", "HEAD"]),
        commit_date=_safe_git(["log", "-1", "--format=%cd", "--date=iso-strict"]),
        remote_url=_safe_git(["remote", "get-url", "origin"]),
    )


async def get_version_info() -> VersionInfo:
    """Асинхронно собирает версию и Git-метаданные."""
    return await asyncio.to_thread(get_version_info_sync)
