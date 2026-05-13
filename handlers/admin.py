"""Обработчики административной панели Telegram-бота."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from keyboards import (
    admin_broadcast_confirmation_keyboard,
    admin_force_check_confirmation_keyboard,
    admin_logs_keyboard,
    admin_news_keyboard,
    admin_news_moderation_keyboard,
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
from services.logs_service import get_log_view, get_update_log_view
from services.system_status_service import get_system_status
from services.update_service import UpdateError, check_updates, is_update_running, start_update
from states import AdminBroadcastState
from services.version_service import get_version_info, read_version
from app.news.airline_sync_service import AirlineSyncService
from app.news.formatters import format_admin_news_card
from app.news.repository import AirlineRepository, NewsRepository, NewsSourceRepository, connect, ensure_news_schema
from app.news.service import NewsCollectionService
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
    view = await get_update_log_view()
    truncated_note = "\n\n<i>Показан только последний фрагмент лога.</i>" if view.truncated else ""
    logger.info("Update log viewed by telegram_id=%s path=%s", _user_id(callback), view.path)
    await callback.message.answer(
        f"{view.title}\n\n"
        f"Статус: <b>{escape(_format_status(state.get('status')))}</b>\n"
        f"Дата запуска: <code>{escape(state.get('started_at') or 'неизвестно')}</code>\n"
        f"Дата завершения: <code>{escape(state.get('finished_at') or 'неизвестно')}</code>\n"
        f"Файл: <code>{escape(view.path)}</code>\n\n"
        f"<pre>{escape(view.text)}</pre>"
        f"{truncated_note}",
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
        f"⏲ Интервал проверки: <b>{escape(status.price_check_interval)}</b>\n"
        f"🧾 Уровень логирования: <b>{escape(status.log_level)}</b>\n"
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


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрашивает текст для массовой рассылки пользователям."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await state.set_state(AdminBroadcastState.waiting_text)
    await callback.message.answer(
        "📣 <b>Рассылка пользователям</b>\n\n"
        "Отправьте текст сообщения одним следующим сообщением.\n"
        "Для отмены используйте /cancel или кнопку отмены на предпросмотре.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminBroadcastState.waiting_text, Command("cancel"))
@router.message(AdminBroadcastState.waiting_confirmation, Command("cancel"))
async def broadcast_cancel_command(message: Message, state: FSMContext) -> None:
    """Отменяет подготовку рассылки командой /cancel."""
    await state.clear()
    if not is_admin(_user_id(message)):
        await _deny_message(message)
        return
    await message.answer("❌ Рассылка отменена.", reply_markup=admin_panel_keyboard())


@router.message(AdminBroadcastState.waiting_text)
async def broadcast_text_received(message: Message, state: FSMContext) -> None:
    """Показывает предпросмотр рассылки и просит подтверждение."""
    if not is_admin(_user_id(message)):
        await state.clear()
        await _deny_message(message)
        return

    text = (message.text or message.html_text or "").strip()
    if not text:
        await message.answer("⚠️ Текст рассылки не должен быть пустым. Отправьте сообщение ещё раз или /cancel.")
        return
    if len(text) > 4000:
        await message.answer("⚠️ Сообщение слишком длинное для безопасной отправки. Сократите текст до 4000 символов.")
        return

    await state.update_data(broadcast_text=text)
    await state.set_state(AdminBroadcastState.waiting_confirmation)
    await message.answer(
        "👀 <b>Предпросмотр рассылки</b>\n\n"
        f"{escape(text)}\n\n"
        "Подтвердите отправку всем пользователям.",
        parse_mode="HTML",
        reply_markup=admin_broadcast_confirmation_keyboard(),
    )


@router.callback_query(AdminBroadcastState.waiting_confirmation, F.data == "admin:broadcast_confirm")
async def broadcast_confirm_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Отправляет подтвержденную рассылку всем известным пользователям."""
    if not is_admin(_user_id(callback)):
        await state.clear()
        await _deny_callback(callback)
        return

    data = await state.get_data()
    text = data.get("broadcast_text")
    if not text:
        await state.clear()
        await callback.answer("Текст рассылки не найден", show_alert=True)
        return

    user_ids = await db.list_all_user_ids()
    success = 0
    failed = 0
    await callback.message.answer(f"⏳ Рассылка запущена. Получателей: {len(user_ids)}")
    for user_id in user_ids:
        try:
            await callback.bot.send_message(user_id, text, disable_web_page_preview=True)
            success += 1
        except Exception as exc:  # noqa: BLE001 - ошибка одного получателя не останавливает рассылку.
            failed += 1
            logger.warning("Broadcast send failed user=%s: %s", user_id, exc)

    await db.record_bot_event(_user_id(callback), "admin_broadcast", f"success={success};failed={failed}")
    await state.clear()
    await callback.message.answer(
        "📣 <b>Рассылка завершена</b>\n\n"
        f"✅ Успешно отправлено: <b>{success}</b>\n"
        f"❌ Ошибок отправки: <b>{failed}</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_keyboard(),
    )
    await callback.answer()


@router.callback_query(AdminBroadcastState.waiting_confirmation, F.data == "admin:broadcast_cancel")
async def broadcast_cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Отменяет подготовленную рассылку."""
    if not is_admin(_user_id(callback)):
        await state.clear()
        await _deny_callback(callback)
        return
    await state.clear()
    await callback.message.answer("❌ Рассылка отменена.", reply_markup=admin_panel_keyboard())
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


@router.callback_query(F.data == "admin:news")
async def admin_news_callback(callback: CallbackQuery) -> None:
    """Shows news administration entry point."""
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.message.answer("📰 <b>Новости</b>\nВыберите раздел:", parse_mode="HTML", reply_markup=admin_news_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:news:airlines")
async def admin_news_airlines_callback(callback: CallbackQuery) -> None:
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    with connect() as connection:
        ensure_news_schema(connection)
        stats = AirlineRepository(connection).stats()
    text = (
        "✈️ <b>Авиакомпании</b>\n\n"
        f"Всего: <b>{stats.get('total', 0)}</b>\n"
        f"Российских: <b>{stats.get('russian', 0)}</b>\n"
        f"Активных: <b>{stats.get('active', 0)}</b>\n"
        f"С источниками новостей: <b>{stats.get('with_sources', 0)}</b>\n"
        f"Без источников: <b>{stats.get('without_sources', 0)}</b>\n"
        f"Встречались в билетах: <b>{stats.get('seen_in_tickets', 0)}</b>"
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_news_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:news:sources")
async def admin_news_sources_callback(callback: CallbackQuery) -> None:
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    with connect() as connection:
        ensure_news_schema(connection)
        sources = NewsSourceRepository(connection).get_active_sources()[:30]
    lines = ["📡 <b>Активные источники новостей</b>", ""]
    if not sources:
        lines.append("Источники пока не настроены.")
    for source in sources:
        lines.append(f"• {escape(str(source.get('airline_name')))} · {escape(str(source.get('source_role')))} · {escape(str(source.get('source_type')))}")
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=admin_news_keyboard(), disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data == "admin:news:pending")
async def admin_news_pending_callback(callback: CallbackQuery) -> None:
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    with connect() as connection:
        ensure_news_schema(connection)
        pending = NewsRepository(connection).get_pending(limit=5)
    if not pending:
        await callback.message.answer("⏳ Новостей на модерации нет.", reply_markup=admin_news_keyboard())
    else:
        for news in pending:
            await callback.message.answer(format_admin_news_card(news), parse_mode="HTML", reply_markup=admin_news_moderation_keyboard(int(news["id"])), disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data.in_({"admin:news:approved", "admin:news:rejected"}))
async def admin_news_status_list_callback(callback: CallbackQuery) -> None:
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    status = "approved" if callback.data.endswith("approved") else "rejected"
    with connect() as connection:
        ensure_news_schema(connection)
        rows = [dict(row) for row in connection.execute("SELECT * FROM airline_news WHERE status = ? ORDER BY updated_at DESC LIMIT 10", (status,))]
    lines = [f"<b>{'✅ Одобренные' if status == 'approved' else '🚫 Отклонённые'} новости</b>", ""]
    lines.extend(f"• #{row['id']} {escape(str(row.get('airline_name')))} — {escape(str(row.get('title_original'))[:90])}" for row in rows)
    if not rows:
        lines.append("Пока пусто.")
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=admin_news_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:news:stats")
async def admin_news_stats_callback(callback: CallbackQuery) -> None:
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    with connect() as connection:
        ensure_news_schema(connection)
        airline_stats = AirlineRepository(connection).stats()
        news_stats = NewsRepository(connection).stats()
        by_category = connection.execute("SELECT COALESCE(category, 'uncategorized') c, COUNT(*) n FROM airline_news GROUP BY category ORDER BY n DESC").fetchall()
    lines = [
        "📊 <b>Статистика новостей</b>", "",
        f"Источников всего: <b>{news_stats.get('sources_total', 0)}</b>",
        f"Активных источников: <b>{news_stats.get('sources_active', 0)}</b>",
        f"Российских авиакомпаний: <b>{airline_stats.get('russian', 0)}</b>",
        f"Российских с источниками: <b>{airline_stats.get('with_sources', 0)}</b>",
        f"Авиакомпаний в билетах: <b>{airline_stats.get('seen_in_tickets', 0)}</b>",
        f"Новостей всего: <b>{news_stats.get('total', 0)}</b>",
        f"На модерации: <b>{news_stats.get('pending', 0)}</b>",
        f"Опубликовано: <b>{news_stats.get('published', 0)}</b>",
        f"Отклонено: <b>{news_stats.get('rejected', 0)}</b>",
        f"Доставок за сутки: <b>{news_stats.get('deliveries_24h', 0)}</b>", "", "По категориям:",
    ]
    lines.extend(f"• {row['c']}: {row['n']}" for row in by_category)
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=admin_news_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:news:collect")
async def admin_news_collect_callback(callback: CallbackQuery) -> None:
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.answer("Запускаю сбор новостей…")
    result = await NewsCollectionService().collect_due_sources(limit=10, concurrency=2)
    created = sum(int(item.get("created", 0)) for item in result)
    fetched = sum(int(item.get("fetched", 0)) for item in result)
    await callback.message.answer(f"🔄 Сбор завершён. Источников: {len(result)}, найдено: {fetched}, новых: {created}.", reply_markup=admin_news_keyboard())


@router.callback_query(F.data == "admin:news:sync_airlines")
async def admin_news_sync_airlines_callback(callback: CallbackQuery) -> None:
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    await callback.answer("Запускаю синхронизацию…")
    try:
        result = await AirlineSyncService().sync()
    except Exception as error:  # noqa: BLE001
        logger.exception("Manual airline sync failed")
        await callback.message.answer(f"❌ Ошибка синхронизации: {escape(str(error))}", parse_mode="HTML", reply_markup=admin_news_keyboard())
        return
    await callback.message.answer(
        "🔁 <b>Синхронизация завершена</b>\n"
        f"Загружено: <b>{result.get('loaded', 0)}</b>\n"
        f"Создано: <b>{result.get('created', 0)}</b>\n"
        f"Обновлено: <b>{result.get('updated', 0)}</b>\n"
        f"Российских в справочнике: <b>{result.get('russian', 0)}</b>",
        parse_mode="HTML",
        reply_markup=admin_news_keyboard(),
    )


@router.callback_query(F.data.startswith("admin:news:publish:"))
async def admin_news_publish_callback(callback: CallbackQuery) -> None:
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    news_id = int(callback.data.rsplit(":", 1)[-1])
    await NewsCollectionService().publish_news(news_id, "approved by admin")
    await callback.message.answer(f"✅ Новость #{news_id} опубликована.", reply_markup=admin_news_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:news:reject:"))
async def admin_news_reject_callback(callback: CallbackQuery) -> None:
    if not is_admin(_user_id(callback)):
        await _deny_callback(callback)
        return
    news_id = int(callback.data.rsplit(":", 1)[-1])
    with connect() as connection:
        ensure_news_schema(connection)
        NewsRepository(connection).update_status(news_id, "rejected", "rejected by admin")
        connection.commit()
    await callback.message.answer(f"❌ Новость #{news_id} отклонена.", reply_markup=admin_news_keyboard())
    await callback.answer()
