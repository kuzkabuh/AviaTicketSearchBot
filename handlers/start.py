"""Стартовые команды, language onboarding and main-menu callbacks."""

from datetime import date

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards import currency_keyboard, language_keyboard, news_card_keyboard, news_menu_keyboard, news_subscriptions_keyboard, settings_keyboard, start_search_keyboard
import db
from services.i18n import defaults_for_language, t, translate, user_language
from app.news.digest_service import personalized_collection
from app.news.formatters import format_news_card
from app.news.repository import NewsRepository, NewsSubscriptionRepository, connect, ensure_news_schema
from services.calendar_keyboard import build_calendar_keyboard
from states import PopularDirectionState, TicketSearchState
from utils.admin_access import is_admin

router = Router(name="start")


async def _show_main_menu(message: Message, user_id: int | None) -> None:
    language = await user_language(user_id)
    await message.answer(
        translate(language, "welcome"),
        reply_markup=start_search_keyboard(is_admin=is_admin(user_id), language_code=language),
    )


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
    """Shows language choice on first start and localized menu afterwards."""
    await state.clear()
    user_id = message.from_user.id if message.from_user else None
    await db.record_bot_event(user_id, "bot_start")
    profile = await db.get_user_profile(user_id) if user_id else None
    if not profile or not profile.get("language_code"):
        await message.answer(translate("ru", "language.select"), reply_markup=language_keyboard())
        return
    await _show_main_menu(message, user_id)


@router.callback_query(F.data.startswith("settings:language:set:"))
async def set_language(callback: CallbackQuery) -> None:
    """Saves selected language and applies language-specific defaults."""
    language = (callback.data or "").split(":")[-1]
    currency, market = defaults_for_language(language)
    await db.update_user_preferences(callback.from_user.id, language_code=language, currency_code=currency, market_code=market)
    await callback.message.answer(translate(language, "language.changed"))
    await _show_main_menu(callback.message, callback.from_user.id)
    await callback.answer()


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    """Sends localized usage help."""
    user_id = message.from_user.id if message.from_user else None
    language = await user_language(user_id)
    await message.answer(
        translate(language, "welcome")
        + "\n\n/search — step-by-step search\nType a phrase like: Москва Сочи 20 июня 2 взрослых / Find flights from Amsterdam to London on July 15."
    )


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    """Cancels current FSM dialog."""
    current_state = await state.get_state()
    await state.clear()
    language = await user_language(message.from_user.id if message.from_user else None)
    if current_state:
        await message.answer("✅ " + ("Текущий ввод отменен." if language == "ru" else "Current input cancelled."))
    else:
        await message.answer("/search")


@router.callback_query(F.data == "menu:settings")
async def menu_settings(callback: CallbackQuery) -> None:
    profile = await db.get_user_profile(callback.from_user.id) or {}
    language = await user_language(callback.from_user.id)
    await callback.message.answer(
        translate(language, "settings.title", language=profile.get("language_code", language), currency=profile.get("currency_code", "RUB")),
        reply_markup=settings_keyboard(language),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:language")
async def choose_language(callback: CallbackQuery) -> None:
    language = await user_language(callback.from_user.id)
    await callback.message.answer(translate(language, "language.select"), reply_markup=language_keyboard())
    await callback.answer()


@router.callback_query(F.data == "settings:currency")
async def choose_currency(callback: CallbackQuery) -> None:
    language = await user_language(callback.from_user.id)
    await callback.message.answer(translate(language, "currency.select"), reply_markup=currency_keyboard(language))
    await callback.answer()


@router.callback_query(F.data.startswith("settings:currency:set:"))
async def set_currency(callback: CallbackQuery) -> None:
    currency = (callback.data or "").split(":")[-1].upper()
    await db.update_user_preferences(callback.from_user.id, currency_code=currency)
    language = await user_language(callback.from_user.id)
    await callback.message.answer(translate(language, "currency.changed", currency=currency))
    await callback.answer()


@router.callback_query(F.data == "settings:back")
async def settings_back(callback: CallbackQuery) -> None:
    await _show_main_menu(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "menu:search")
async def menu_search(callback: CallbackQuery, state: FSMContext) -> None:
    """Starts step-by-step search from main menu."""
    await state.clear()
    await state.set_state(TicketSearchState.waiting_origin)
    await callback.message.answer(await t(callback.from_user.id, "search.origin_prompt"))
    await callback.answer()


@router.callback_query(F.data == "menu:smart_search")
async def menu_smart_search(callback: CallbackQuery) -> None:
    language = await user_language(callback.from_user.id)
    example = "Найди билеты из Москвы в Казань с 15 мая по 26 мая для 2 взрослых" if language == "ru" else "Find flights from Amsterdam to London on July 15 for 1 adult"
    await callback.message.answer(example)
    await callback.answer()


@router.callback_query(F.data == "menu:popular")
async def menu_popular(callback: CallbackQuery, state: FSMContext) -> None:
    """Starts popular destinations scenario."""
    await state.clear()
    await state.set_state(PopularDirectionState.waiting_origin)
    await callback.message.answer("Введите город, аэропорт или IATA-код отправления для популярных направлений:")
    await callback.answer()


@router.callback_query(F.data == "menu:news")
async def menu_news(callback: CallbackQuery) -> None:
    language = await user_language(callback.from_user.id)
    await callback.message.answer(translate(language, "news.menu.title"), reply_markup=news_menu_keyboard(language))
    await callback.answer()


@router.callback_query(F.data.startswith("news:list:"))
async def news_list(callback: CallbackQuery) -> None:
    language = await user_language(callback.from_user.id)
    selector = callback.data.rsplit(":", 1)[-1]
    with connect() as connection:
        ensure_news_schema(connection)
        repo = NewsRepository(connection)
        if selector == "russian":
            rows = repo.list_published(russian_only=True, limit=5)
        else:
            rows = repo.list_published(category=selector, limit=5)
    if not rows:
        await callback.message.answer(translate(language, "news.errors.empty"), reply_markup=news_menu_keyboard(language))
    else:
        for news in rows:
            await callback.message.answer(format_news_card(news, language), parse_mode="HTML", disable_web_page_preview=True, reply_markup=news_card_keyboard(news, language))
    await callback.answer()


@router.callback_query(F.data == "news:for_you")
async def news_for_you(callback: CallbackQuery) -> None:
    language = await user_language(callback.from_user.id)
    await callback.message.answer(personalized_collection(callback.from_user.id, language), reply_markup=news_menu_keyboard(language))
    await callback.answer()


@router.callback_query(F.data == "news:subscriptions")
async def news_subscriptions(callback: CallbackQuery) -> None:
    language = await user_language(callback.from_user.id)
    await callback.message.answer(translate(language, "news.subscriptions.title"), reply_markup=news_subscriptions_keyboard(language))
    await callback.answer()


@router.callback_query(F.data.startswith("news:sub:"))
async def news_subscribe_type(callback: CallbackQuery) -> None:
    language = await user_language(callback.from_user.id)
    subscription_type = callback.data.rsplit(":", 1)[-1]
    with connect() as connection:
        ensure_news_schema(connection)
        NewsSubscriptionRepository(connection).upsert_subscription(callback.from_user.id, subscription_type)
        connection.commit()
    await callback.message.answer(translate(language, "news.subscriptions.saved"), reply_markup=news_menu_keyboard(language))
    await callback.answer()


@router.callback_query(F.data.startswith("news:subcat:"))
async def news_subscribe_category(callback: CallbackQuery) -> None:
    language = await user_language(callback.from_user.id)
    category = callback.data.rsplit(":", 1)[-1]
    with connect() as connection:
        ensure_news_schema(connection)
        NewsSubscriptionRepository(connection).upsert_subscription(callback.from_user.id, "category", category=category)
        connection.commit()
    await callback.message.answer(translate(language, "news.subscriptions.saved"), reply_markup=news_menu_keyboard(language))
    await callback.answer()


@router.callback_query(F.data.startswith("news:search:"))
async def news_search(callback: CallbackQuery, state: FSMContext) -> None:
    language = await user_language(callback.from_user.id)
    news_id = int(callback.data.rsplit(":", 1)[-1])
    with connect() as connection:
        ensure_news_schema(connection)
        news = NewsRepository(connection).get_by_id(news_id)
    if not news or not news.get("related_destination_iata"):
        await callback.message.answer(translate(language, "news.errors.route_missing"))
        await callback.answer()
        return
    if not news.get("related_origin_iata"):
        await state.clear()
        await state.set_state(TicketSearchState.waiting_origin)
        await state.update_data(destination=news.get("related_destination_iata"), destination_location={"code": news.get("related_destination_iata"), "city": news.get("related_destination_name") or news.get("related_destination_iata")})
        await callback.message.answer(translate(language, "news.cards.choose_origin"))
        await callback.answer()
        return
    await state.clear()
    await state.set_state(TicketSearchState.waiting_date)
    await state.update_data(
        origin=news.get("related_origin_iata"),
        destination=news.get("related_destination_iata"),
        origin_location={"code": news.get("related_origin_iata"), "city": news.get("related_origin_name") or news.get("related_origin_iata")},
        destination_location={"code": news.get("related_destination_iata"), "city": news.get("related_destination_name") or news.get("related_destination_iata")},
        trip_type="one_way",
    )
    today = date.today()
    await callback.message.answer(translate(language, "calendar.departure"), reply_markup=build_calendar_keyboard(year=today.year, month=today.month, mode="departure", language_code=language, min_date=today))
    await callback.answer()
