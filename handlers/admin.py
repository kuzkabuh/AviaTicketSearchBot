"""Обработчики административной панели Telegram-бота."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from config import settings
from keyboards import admin_panel_keyboard, start_search_keyboard, update_confirmation_keyboard
from services.update_service import UpdateError, check_updates, is_update_running, start_update
from services.version_service import get_version_info, read_version
from utils.admin_access import is_admin
from utils.update_state import mark_update_notified, read_update_state

router = Router(name="admin")
logger = logging.getLogger(__name__)

NO_ACCESS_TEXT = "⛔ У вас нет доступа к административному разделу."
ADMIN_PANEL_TEXT = "⚙️ <b>Административная панель</b>\nВыберите действие:"


def _user_id(message_or_callback: Message | CallbackQuery) -> int | None:
    return message_or_callback.from_user.id if message_or_callback.from_user else None


async def _deny_message(message: Message) -> None:
    logger.warning("Unauthorized admin command attempt: telegram_id=%s", _user_id(message))
    await message.answer(NO_ACCESS_TEXT)


async def _deny_callback(callback: CallbackQuery) -> None:
    logger.warning("Unauthorized admin callback attempt: telegram_id=%s", _user_id(callback))
    await callback.answer(NO_ACCESS_TEXT, show_alert=True)


def _tail_update_log(max_lines: int = 50) -> str:
    log_path = Path(settings.bot_update_log_path)
    if not log_path.exists():
        return "Лог обновления пока отсутствует."

    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as error:
        return f"Не удалось прочитать лог обновления: {error}"

    return "\n".join(lines[-max_lines:]) or "Лог обновления пуст."


def _format_status(status: str | None) -> str:
    statuses = {
        "success": "успешно",
        "error": "ошибка",
        "no_updates": "обновлений не было",
        "in_progress": "выполняется",
    }
    return statuses.get(status or "", status or "неизвестно")


@router.message(Command("admin"))
async def admin_command(message: Message) -> None:
    """Открывает административную панель для разрешенных администраторов."""
    if not is_admin(_user_id(message)):
        await _deny_message(message)
        return

    logger.info("Admin panel opened by telegram_id=%s", _user_id(message))
    await message.answer(ADMIN_PANEL_TEXT, parse_mode="HTML", reply_markup=admin_panel_keyboard())


@router.callback_query(F.data == "menu:admin")
async def admin_menu_callback(callback: CallbackQuery) -> None:
    """Открывает административную панель из главного меню."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return

    logger.info("Admin panel opened from menu by telegram_id=%s", _user_id(callback))
    await callback.message.answer(ADMIN_PANEL_TEXT, parse_mode="HTML", reply_markup=admin_panel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:version")
async def version_callback(callback: CallbackQuery) -> None:
    """Показывает текущую версию бота и Git-информацию."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return

    info = await get_version_info()
    logger.info("Bot version viewed by telegram_id=%s", _user_id(callback))
    await callback.message.answer(
        "🤖 <b>Текущая версия бота:</b> "
        f"<code>{escape(info.version)}</code>\n"
        f"📂 Ветка репозитория: <code>{escape(info.branch)}</code>\n"
        f"🖥 Путь проекта: <code>{escape(info.project_dir)}</code>\n"
        f"🔖 Commit: <code>{escape(info.commit_hash)}</code>\n"
        f"🕒 Дата commit: <code>{escape(info.commit_date)}</code>\n"
        f"🌐 Репозиторий: <code>{escape(info.remote_url)}</code>",
        parse_mode="HTML",
        reply_markup=admin_panel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:check_updates")
async def check_updates_callback(callback: CallbackQuery) -> None:
    """Проверяет наличие новых коммитов в удаленной ветке."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return

    await callback.answer("Проверяю обновления…")
    try:
        result = await check_updates()
    except UpdateError as error:
        logger.exception("Admin update check failed: telegram_id=%s", _user_id(callback))
        await callback.message.answer(
            "❌ Не удалось проверить обновления.\n"
            f"Ошибка: <code>{escape(str(error))}</code>",
            parse_mode="HTML",
            reply_markup=admin_panel_keyboard(),
        )
        return

    if not result.has_updates:
        logger.info("No updates found by telegram_id=%s", _user_id(callback))
        await callback.message.answer(
            "✅ Обновления не найдены.\nУстановлена актуальная версия бота.",
            reply_markup=admin_panel_keyboard(),
        )
        return

    logger.info("Updates found by telegram_id=%s: behind=%s", _user_id(callback), result.commits_behind)
    latest_message = f"\nПоследний commit: <code>{escape(result.latest_message)}</code>" if result.latest_message else ""
    await callback.message.answer(
        "🆕 <b>Найдена новая версия бота</b>\n\n"
        f"Локальный commit: <code>{escape(result.local_commit)}</code>\n"
        f"Новый commit: <code>{escape(result.remote_commit)}</code>\n"
        f"Доступно новых коммитов: <code>{result.commits_behind}</code>"
        f"{latest_message}\n\n"
        "Для установки нажмите кнопку <b>«⬆️ Обновить бота»</b>.",
        parse_mode="HTML",
        reply_markup=admin_panel_keyboard(),
    )


@router.callback_query(F.data == "admin:update")
async def update_callback(callback: CallbackQuery) -> None:
    """Запрашивает подтверждение перед запуском обновления."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return

    if await is_update_running():
        logger.warning("Repeated update start attempt: telegram_id=%s", _user_id(callback))
        await callback.answer("⚠️ Обновление уже выполняется. Дождитесь завершения текущего процесса.", show_alert=True)
        return

    await callback.message.answer(
        "⚠️ <b>Подтвердите обновление бота</b>\n\n"
        "Будет выполнено:\n\n"
        "• получение нового кода из репозитория;\n"
        "• обновление зависимостей;\n"
        "• применение миграций, если они предусмотрены;\n"
        "• перезапуск сервиса бота.\n\n"
        "Продолжить?",
        parse_mode="HTML",
        reply_markup=update_confirmation_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:update_confirm")
async def update_confirm_callback(callback: CallbackQuery) -> None:
    """Запускает фоновый сценарий обновления."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return

    telegram_id = _user_id(callback)
    if telegram_id is None:
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return

    try:
        await start_update(telegram_id)
    except UpdateError as error:
        if str(error) == "update_already_running":
            await callback.answer("⚠️ Обновление уже выполняется. Дождитесь завершения текущего процесса.", show_alert=True)
            return
        logger.exception("Failed to start update: telegram_id=%s", telegram_id)
        await callback.message.answer(
            "❌ Не удалось запустить обновление.\n"
            f"Ошибка: <code>{escape(str(error))}</code>",
            parse_mode="HTML",
            reply_markup=admin_panel_keyboard(),
        )
        await callback.answer()
        return

    logger.info("Update started by telegram_id=%s", telegram_id)
    await callback.message.answer(
        "⏳ Обновление запущено.\n"
        "Бот применит новую версию и перезапустится. После запуска я сообщу результат обновления."
    )
    await callback.answer()


@router.callback_query(F.data == "admin:update_cancel")
async def update_cancel_callback(callback: CallbackQuery) -> None:
    """Отменяет запуск обновления."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return

    await callback.message.answer("❌ Обновление отменено.", reply_markup=admin_panel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:update_log")
async def update_log_callback(callback: CallbackQuery) -> None:
    """Показывает последние строки лога обновления."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return

    state = await read_update_state()
    log_text = _tail_update_log()
    logger.info("Update log viewed by telegram_id=%s", _user_id(callback))
    await callback.message.answer(
        "📋 <b>Последний лог обновления</b>\n\n"
        f"Статус: <b>{escape(_format_status(state.get('status')))}</b>\n"
        f"Дата запуска: <code>{escape(state.get('started_at') or 'неизвестно')}</code>\n"
        f"Дата завершения: <code>{escape(state.get('finished_at') or 'неизвестно')}</code>\n\n"
        f"<pre>{escape(log_text)}</pre>",
        parse_mode="HTML",
        reply_markup=admin_panel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:main_menu")
async def admin_main_menu_callback(callback: CallbackQuery) -> None:
    """Возвращает администратора в главное меню."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return

    await callback.message.answer("Главное меню:", reply_markup=start_search_keyboard(is_admin=True))
    await callback.answer()


async def notify_update_result_on_start(bot) -> None:
    """После рестарта отправляет администратору результат завершенного обновления."""
    state = await read_update_state()
    telegram_id = state.get("telegram_id")
    status = state.get("status")
    if not telegram_id or state.get("notified") or status == "in_progress":
        return

    if status in {"success", "no_updates"}:
        title = "✅ <b>Обновление успешно применено</b>" if status == "success" else "✅ <b>Обновления не требовались</b>"
        text = (
            f"{title}\n\n"
            "Бот обновлён и перезапущен.\n"
            f"Текущая версия: <code>{escape(read_version())}</code>"
        )
    else:
        text = (
            "❌ <b>Во время обновления произошла ошибка</b>\n\n"
            "Обновление не было полностью применено.\n"
            "Проверьте лог обновления в админ-панели."
        )

    try:
        await bot.send_message(int(telegram_id), text, parse_mode="HTML", reply_markup=admin_panel_keyboard())
    except Exception:  # noqa: BLE001 - уведомление не должно ломать старт бота.
        logger.exception("Failed to notify admin about update result")
        return

    state["last_notification_attempt_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    await mark_update_notified()
