"""Хендлеры создания, просмотра и управления подписками."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from handlers.search import get_cached_offer
import db
from keyboards import notification_mode_keyboard, subscriptions_keyboard
from services.subscriptions import check_subscription_price, create_subscription, delete_subscription, get_user_subscriptions
from states import SubscriptionCreateState
from utils.formatters import format_money, format_subscription_list

router = Router(name="subscriptions")

NOTIFICATION_MODE_LABELS = {
    "any_change": "при любом изменении",
    "price_drop": "только при снижении",
    "target_price": "ниже заданной суммы",
}


@router.callback_query(F.data.startswith("sub:create:"))
async def create_subscription_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрашивает режим уведомлений перед созданием подписки."""
    token = (callback.data or "").split(":")[-1]
    cached = get_cached_offer(token, callback.from_user.id)
    if not cached:
        await callback.answer("Вариант устарел. Запустите поиск заново.", show_alert=True)
        return

    await state.clear()
    await callback.message.answer(
        "Как уведомлять вас о цене?",
        reply_markup=notification_mode_keyboard(token),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:mode:"))
async def choose_subscription_notification_mode(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняет выбранный режим уведомлений и создает подписку, если сумма не требуется."""
    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Не удалось прочитать режим уведомлений", show_alert=True)
        return

    _, _, notification_mode, token = parts
    if notification_mode not in NOTIFICATION_MODE_LABELS:
        await callback.answer("Неизвестный режим уведомлений", show_alert=True)
        return

    cached = get_cached_offer(token, callback.from_user.id)
    if not cached:
        await callback.answer("Вариант устарел. Запустите поиск заново.", show_alert=True)
        return

    if notification_mode == "target_price":
        await state.update_data(subscription_token=token, notification_mode=notification_mode)
        await state.set_state(SubscriptionCreateState.waiting_target_price)
        await callback.message.answer(
            "🎯 Введите сумму, ниже которой нужно уведомить о цене. "
            "Обработка суммы будет добавлена в следующем подэтапе."
        )
        await callback.answer()
        return

    created, _ = await create_subscription(
        callback.from_user.id,
        callback.from_user.username,
        cached["offer"],
        cached["passengers"],
        notification_mode,
    )
    if created:
        await db.record_bot_event(callback.from_user.id, "subscription_created", f"notification_mode={notification_mode}")
    if not created:
        await callback.answer("⚠️ Вы уже отслеживаете этот рейс.", show_alert=True)
        return

    mode_label = NOTIFICATION_MODE_LABELS[notification_mode]
    await callback.message.answer(
        "✅ Подписка создана!\n"
        f"Режим уведомлений: {mode_label}.\n"
        "Я буду отслеживать цену на этот перелёт."
    )
    await callback.answer()


@router.message(Command("subscriptions"))
async def subscriptions_command(message: Message) -> None:
    """Показывает активные подписки пользователя."""
    await _show_subscriptions(message)


@router.callback_query(F.data == "menu:subscriptions")
async def subscriptions_menu(callback: CallbackQuery) -> None:
    """Показывает активные подписки из главного меню."""
    await _show_subscriptions(callback.message, callback.from_user.id)
    await callback.answer()


async def _show_subscriptions(message: Message, user_id: int | None = None) -> None:
    """Отправляет список подписок и кнопки управления."""
    target_user_id = user_id or message.from_user.id
    subscriptions = await get_user_subscriptions(target_user_id)
    await message.answer(
        format_subscription_list(subscriptions),
        parse_mode="HTML",
        reply_markup=subscriptions_keyboard(subscriptions) if subscriptions else None,
    )


@router.callback_query(F.data.startswith("sub:check:"))
async def check_subscription_callback(callback: CallbackQuery) -> None:
    """Выполняет ручную проверку цены подписки."""
    subscription_id = int((callback.data or "").split(":")[-1])
    subscriptions = await get_user_subscriptions(callback.from_user.id)
    subscription = next((item for item in subscriptions if item["id"] == subscription_id), None)
    if not subscription:
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    await db.record_bot_event(callback.from_user.id, "manual_price_check", f"subscription={subscription_id}")
    result = await check_subscription_price(subscription, bot=callback.bot, notify=False)
    old_price = result.get("old_price")
    new_price = result.get("new_price")
    currency = subscription.get("currency") or "RUB"

    if result["status"] == "not_found":
        text = "ℹ️ Не удалось найти отслеживаемый рейс по прежним параметрам."
    elif result["status"] == "changed" and old_price is not None and new_price is not None:
        delta = new_price - old_price
        direction = "📉 Цена снизилась" if delta < 0 else "📈 Цена выросла"
        text = (
            "🔄 Проверка выполнена.\n"
            f"Последняя цена: {format_money(old_price, currency)}\n"
            f"Текущая цена: {format_money(new_price, currency)}\n"
            f"{direction} на {format_money(abs(delta), currency)}."
        )
    else:
        text = f"🔄 Проверка выполнена. Цена не изменилась: {format_money(new_price, currency)}."

    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data.startswith("sub:delete:"))
async def delete_subscription_callback(callback: CallbackQuery) -> None:
    """Удаляет подписку пользователя."""
    subscription_id = int((callback.data or "").split(":")[-1])
    deleted = await delete_subscription(subscription_id, callback.from_user.id)
    if not deleted:
        await callback.answer("Подписка не найдена", show_alert=True)
        return
    await db.record_bot_event(callback.from_user.id, "subscription_deleted", f"subscription={subscription_id}")
    await callback.message.answer("✅ Подписка удалена.")
    await callback.answer()
