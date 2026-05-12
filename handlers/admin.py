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
from keyboards import (
    admin_force_check_confirmation_keyboard,
    admin_logs_keyboard,
    admin_panel_keyboard,
    admin_restart_confirmation_keyboard,
    admin_stats_keyboard,
    admin_users_keyboard,
    start_search_keyboard,
    update_confirmation_keyboard,
)
from services.admin_control_service import cleanup_temp_files, force_check_all_subscriptions, restart_bot_service
from services.admin_stats_service import (
    format_latest_users,
    format_overview_statistics,
    format_period_statistics,
    format_popular_routes,
    format_subscription_analytics,
    format_users_summary,
    format_users_with_subscriptions,
)
from services.logs_service import get_log_view
from services.system_status_service import get_system_status
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


@router.callback_query(F.data == "admin:back")
async def admin_back_callback(callback: CallbackQuery) -> None:
    """Возвращает к главной админ-панели из подразделов."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer(ADMIN_PANEL_TEXT, parse_mode="HTML", reply_markup=admin_panel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:logs")
async def logs_menu_callback(callback: CallbackQuery) -> None:
    """Открывает меню просмотра логов."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer("🧾 <b>Логи бота</b>\nВыберите тип логов:", parse_mode="HTML", reply_markup=admin_logs_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:logs:"))
async def log_view_callback(callback: CallbackQuery) -> None:
    """Показывает выбранный фрагмент логов."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    kind = (callback.data or "").split(":")[-1]
    view = await get_log_view(kind)
    body = escape(view.text)
    text = f"{view.title}\n\n{body}" if view.is_empty else f"{view.title}\n\n<pre>{body}</pre>"
    await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_logs_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def stats_callback(callback: CallbackQuery) -> None:
    """Показывает общую статистику бота."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer(await format_overview_statistics(), parse_mode="HTML", reply_markup=admin_stats_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:stats:"))
async def stats_period_callback(callback: CallbackQuery) -> None:
    """Показывает статистику за период или аналитический подраздел."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    section = (callback.data or "").split(":")[-1]
    if section == "routes":
        text = await format_popular_routes()
    elif section == "subscriptions":
        text = await format_subscription_analytics()
    else:
        text = await format_period_statistics(section)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_stats_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:users")
async def users_callback(callback: CallbackQuery) -> None:
    """Показывает сводку по пользователям."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer(await format_users_summary(), parse_mode="HTML", reply_markup=admin_users_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:users:latest")
async def latest_users_callback(callback: CallbackQuery) -> None:
    """Показывает последних пользователей."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer(await format_latest_users(), parse_mode="HTML", reply_markup=admin_users_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:users:subscriptions")
async def users_with_subscriptions_callback(callback: CallbackQuery) -> None:
    """Показывает пользователей с активными подписками."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer(await format_users_with_subscriptions(), parse_mode="HTML", reply_markup=admin_users_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:system")
async def system_status_callback(callback: CallbackQuery) -> None:
    """Показывает состояние сервиса и системы."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    status = await get_system_status()
    await callback.message.answer(
        "🩺 <b>Состояние системы</b>\n\n"
        f"🤖 Сервис бота: <b>{escape(status.service_status)}</b>\n"
        f"⏱ Аптайм приложения: <b>{escape(status.uptime)}</b>\n"
        f"📦 Версия: <code>{escape(status.version)}</code>\n"
        f"🔖 Commit: <code>{escape(status.commit_hash)}</code>\n\n"
        f"🗄 База данных: <b>{escape(status.database_status)}</b>\n"
        f"🔔 Проверка подписок: <b>{escape(status.price_tracking_status)}</b>\n"
        f"📌 Активных подписок: <b>{status.active_subscriptions}</b>\n"
        f"🔒 Lock-файл обновления: <b>{'есть' if status.update_lock_exists else 'нет'}</b>\n\n"
        f"💾 Свободно на диске: <b>{escape(status.disk_free)}</b>\n"
        f"🧠 RAM: <b>{escape(status.ram_usage)}</b>\n"
        f"🖥 CPU load: <b>{escape(status.cpu_load)}</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:restart")
async def restart_callback(callback: CallbackQuery) -> None:
    """Запрашивает подтверждение рестарта сервиса."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer(
        "⚠️ <b>Подтвердите перезапуск сервиса бота.</b>",
        parse_mode="HTML",
        reply_markup=admin_restart_confirmation_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:restart_confirm")
async def restart_confirm_callback(callback: CallbackQuery) -> None:
    """Выполняет подтвержденный рестарт systemd-сервиса."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer("⏳ Рестарт сервиса запущен…")
    ok, output = await restart_bot_service()
    icon = "✅" if ok else "❌"
    await callback.message.answer(f"{icon} Результат рестарта: <code>{escape(output)}</code>", parse_mode="HTML", reply_markup=admin_panel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:restart_cancel")
async def restart_cancel_callback(callback: CallbackQuery) -> None:
    """Отменяет рестарт."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer("❌ Перезапуск отменён.", reply_markup=admin_panel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:cleanup")
async def cleanup_callback(callback: CallbackQuery) -> None:
    """Очищает безопасные временные файлы."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    result = await cleanup_temp_files()
    details = "\n".join(f"• {escape(item)}" for item in result.details[:10])
    await callback.message.answer(
        "🧹 <b>Очистка завершена.</b>\n"
        f"Удалено временных файлов: <b>{result.deleted_files}</b>\n"
        f"Lock-файлов: <b>{result.deleted_locks}</b>\n\n{details}",
        parse_mode="HTML",
        reply_markup=admin_panel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:force_check")
async def force_check_callback(callback: CallbackQuery) -> None:
    """Запрашивает подтверждение внеплановой проверки подписок."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer(
        "⚠️ <b>Подтвердите внеплановую проверку всех активных подписок.</b>",
        parse_mode="HTML",
        reply_markup=admin_force_check_confirmation_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:force_check_confirm")
async def force_check_confirm_callback(callback: CallbackQuery) -> None:
    """Запускает внеплановую проверку подписок."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer("⏳ Проверка активных подписок запущена…")
    result = await force_check_all_subscriptions(callback.bot)
    await callback.message.answer(
        "🔔 <b>Проверка подписок завершена</b>\n\n"
        f"Проверено: <b>{result.checked}</b>\n"
        f"Цен изменилось: <b>{result.changed}</b>\n"
        f"Рейсов не найдено: <b>{result.not_found}</b>\n"
        f"Ошибок: <b>{result.errors}</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:force_check_cancel")
async def force_check_cancel_callback(callback: CallbackQuery) -> None:
    """Отменяет внеплановую проверку."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer("❌ Проверка подписок отменена.", reply_markup=admin_panel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:test_notify")
async def test_notify_callback(callback: CallbackQuery) -> None:
    """Отправляет тестовое уведомление администратору."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer("✅ Тестовое уведомление успешно отправлено.", reply_markup=admin_panel_keyboard())
    await callback.answer("Тестовое уведомление отправлено")


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
