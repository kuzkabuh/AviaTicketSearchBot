"""FSM-хендлеры поиска билетов и популярных направлений."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from api import get_popular_directions
from config import settings
from keyboards import location_choice_keyboard, offer_subscribe_keyboard, popular_directions_keyboard
from services.locations import Location, find_locations, get_location_by_code
from services.tickets import search_ticket_offers
from states import PopularDirectionState, TicketSearchState
from utils.formatters import format_offer
from utils.validators import parse_positive_int, validate_date

router = Router(name="search")

# Короткий in-memory cache нужен только для callback кнопки "Отслеживать цену".
# Постоянные данные подписки сохраняются в SQLite после нажатия пользователем.
OFFER_CACHE: dict[str, dict[str, Any]] = {}


def _cache_offer(user_id: int, offer: dict[str, Any], passengers: int) -> str:
    """Сохраняет вариант выдачи и возвращает короткий token для callback_data."""
    token = uuid4().hex[:16]
    OFFER_CACHE[token] = {"user_id": user_id, "offer": offer, "passengers": passengers}
    return token


def get_cached_offer(token: str, user_id: int) -> dict[str, Any] | None:
    """Возвращает сохраненный вариант, если он принадлежит пользователю."""
    cached = OFFER_CACHE.get(token)
    if not cached or cached.get("user_id") != user_id:
        return None
    return cached


async def _ask_location(message: Message, state: FSMContext, query: str, kind: str) -> Location | None:
    """Ищет локацию или предлагает пользователю выбрать вариант inline-кнопками."""
    locations = find_locations(query)
    if not locations:
        await message.answer(
            "❌ Не удалось найти город или аэропорт. Введите IATA-код, город или аэропорт, например: MOW, Москва, Шереметьево."
        )
        return None

    if len(locations) == 1:
        return locations[0]

    await state.update_data(location_kind=kind)
    await state.set_state(TicketSearchState.choosing_origin if kind == "origin" else TicketSearchState.choosing_destination)
    await message.answer("Нашел несколько вариантов. Выберите нужный:", reply_markup=location_choice_keyboard(kind, locations))
    return None


async def _store_location_and_advance(target: Message | CallbackQuery, state: FSMContext, kind: str, location: Location) -> None:
    """Сохраняет выбранную локацию и переводит сценарий к следующему шагу."""
    message = target.message if isinstance(target, CallbackQuery) else target
    if kind == "origin":
        await state.update_data(origin=location.code, origin_location=location.as_dict())
        await state.set_state(TicketSearchState.waiting_destination)
        await message.answer("Куда летим? Укажите город, аэропорт или IATA-код.")
        return

    data = await state.get_data()
    if location.code == data.get("origin"):
        await message.answer("❌ Город или аэропорт назначения должен отличаться от пункта отправления.")
        await state.set_state(TicketSearchState.waiting_destination)
        return

    await state.update_data(destination=location.code, destination_location=location.as_dict())
    await state.set_state(TicketSearchState.waiting_date)
    await message.answer("Введите дату вылета в формате YYYY-MM-DD, например 2026-06-15:")


async def _send_offers(message: Message, origin: str, destination: str, departure_date: str, passengers: int) -> None:
    """Выполняет асинхронный поиск и отправляет пользователю найденные варианты."""
    await message.answer(f"🔍 Ищу билеты {origin} → {destination} на {departure_date}. Количество билетов: {passengers}...")
    offers = await search_ticket_offers(origin, destination, departure_date)

    if not offers:
        await message.answer("😔 Билеты не найдены. Попробуйте другую дату или другой маршрут.")
        return

    if len(offers) < settings.min_ticket_results:
        await message.answer(f"Нашел {len(offers)} вариант(а). API не вернул достаточно предложений для минимальных {settings.min_ticket_results}.")

    for index, offer in enumerate(offers[: settings.ticket_results_limit], start=1):
        token = _cache_offer(message.from_user.id, offer, passengers)
        await message.answer(
            format_offer(offer, index, passengers),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=offer_subscribe_keyboard(token),
        )


@router.message(Command("search"))
async def search_command(message: Message, state: FSMContext) -> None:
    """Начинает FSM-сценарий поиска и запрашивает пункт отправления."""
    await state.clear()
    await state.set_state(TicketSearchState.waiting_origin)
    await message.answer("Откуда вылетаете? Укажите город, аэропорт или IATA-код.")


@router.message(TicketSearchState.waiting_origin)
async def process_origin(message: Message, state: FSMContext) -> None:
    """Определяет пункт отправления по коду, городу или аэропорту."""
    location = await _ask_location(message, state, message.text or "", "origin")
    if location:
        await _store_location_and_advance(message, state, "origin", location)


@router.callback_query(TicketSearchState.choosing_origin, F.data.startswith("loc:origin:"))
async def choose_origin(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняет выбранный пользователем пункт отправления."""
    code = (callback.data or "").split(":")[-1]
    location = get_location_by_code(code)
    if not location:
        await callback.answer("Не удалось выбрать пункт", show_alert=True)
        return
    await _store_location_and_advance(callback, state, "origin", location)
    await callback.answer()


@router.message(TicketSearchState.waiting_destination)
async def process_destination(message: Message, state: FSMContext) -> None:
    """Определяет пункт назначения по коду, городу или аэропорту."""
    location = await _ask_location(message, state, message.text or "", "destination")
    if location:
        await _store_location_and_advance(message, state, "destination", location)


@router.callback_query(TicketSearchState.choosing_destination, F.data.startswith("loc:destination:"))
async def choose_destination(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняет выбранный пользователем пункт назначения."""
    code = (callback.data or "").split(":")[-1]
    location = get_location_by_code(code)
    if not location:
        await callback.answer("Не удалось выбрать пункт", show_alert=True)
        return
    await _store_location_and_advance(callback, state, "destination", location)
    await callback.answer()


@router.message(TicketSearchState.waiting_date)
async def process_date(message: Message, state: FSMContext) -> None:
    """Проверяет дату и запрашивает количество билетов."""
    departure_date = (message.text or "").strip()

    if not validate_date(departure_date):
        await message.answer("❌ Неверная дата. Используйте формат YYYY-MM-DD; дата должна быть от завтра до 365 дней вперед.")
        return

    await state.update_data(departure_date=departure_date)
    await state.set_state(TicketSearchState.waiting_passengers)
    await message.answer("Сколько билетов нужно?")


@router.message(TicketSearchState.waiting_passengers)
async def process_passengers(message: Message, state: FSMContext) -> None:
    """Валидирует количество билетов, выполняет поиск и завершает FSM-сценарий."""
    passengers = parse_positive_int(message.text)
    if passengers is None:
        await message.answer("⚠️ Укажите количество билетов целым числом, например: 1, 2 или 3.")
        return

    data = await state.get_data()
    await _send_offers(message, data["origin"], data["destination"], data["departure_date"], passengers)
    await state.clear()


@router.message(Command("popular"))
async def popular_command(message: Message, state: FSMContext) -> None:
    """Начинает FSM-сценарий популярных направлений."""
    await state.clear()
    await state.set_state(PopularDirectionState.waiting_origin)
    await message.answer("Введите город, аэропорт или IATA-код отправления для популярных направлений:")


@router.message(PopularDirectionState.waiting_origin)
async def process_popular_origin(message: Message, state: FSMContext) -> None:
    """Получает популярные направления и показывает их inline-кнопками."""
    locations = find_locations(message.text)
    if not locations:
        await message.answer("❌ Не удалось найти пункт отправления. Попробуйте MOW, Москва или LED.")
        return
    if len(locations) > 1:
        await state.set_state(PopularDirectionState.choosing_origin)
        await message.answer("Выберите пункт отправления:", reply_markup=location_choice_keyboard("popular_origin", locations))
        return
    await _send_popular_directions(message, state, locations[0].code)


@router.callback_query(PopularDirectionState.choosing_origin, F.data.startswith("loc:popular_origin:"))
async def choose_popular_origin(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняет выбранный пункт отправления для популярных направлений."""
    code = (callback.data or "").split(":")[-1]
    await _send_popular_directions(callback.message, state, code)
    await callback.answer()


async def _send_popular_directions(message: Message, state: FSMContext, origin: str) -> None:
    """Запрашивает и отправляет популярные направления."""
    await message.answer(f"🔥 Получаю популярные направления из {origin}...")
    directions = await get_popular_directions(origin, limit=5)

    if not directions:
        await message.answer("Не удалось найти популярные направления. Попробуйте другой город отправления.")
        await state.clear()
        return

    await state.update_data(origin=origin)
    await state.set_state(PopularDirectionState.waiting_choice)
    await message.answer(
        "Выберите направление. После выбора я попрошу дату вылета и количество билетов:",
        reply_markup=popular_directions_keyboard(origin, directions),
    )


@router.callback_query(PopularDirectionState.waiting_choice, F.data.startswith("popular:"))
async def process_popular_choice(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняет выбранное популярное направление и переводит пользователя к вводу даты."""
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Не удалось прочитать направление", show_alert=True)
        return

    _, origin, destination = parts
    await state.update_data(origin=origin, destination=destination)
    await state.set_state(TicketSearchState.waiting_date)
    await callback.message.answer(f"Вы выбрали маршрут {origin} → {destination}.\nВведите дату вылета в формате YYYY-MM-DD, например 2026-06-15:")
    await callback.answer()
