"""FSM-хендлеры поиска билетов и популярных направлений."""

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from api import get_popular_directions, search_cheap_tickets
from keyboards import location_options_keyboard, popular_directions_keyboard
from services.locations import find_locations
from states import PopularDirectionState, TicketSearchState
from utils.formatters import format_ticket_offers
from utils.validators import parse_positive_int, validate_date, validate_location_query

router = Router(name="search")


async def _resolve_location_or_ask_choice(
    message: Message,
    state: FSMContext,
    query: str,
    *,
    field: str,
    next_state: Any,
    choice_state: Any,
) -> dict[str, str] | None:
    """
    Определяет IATA-код по коду, названию города или аэропорта.

    Если найден ровно один вариант — возвращает его сразу. Если вариантов
    несколько, сохраняет список в FSMContext и показывает inline-кнопки выбора.
    """
    if not validate_location_query(query):
        await message.answer(
            "❌ Введите IATA-код или название города/аэропорта: например MOW, Москва, Казань или Пулково."
        )
        return None

    options = await find_locations(query, limit=5)
    if not options:
        await message.answer(
            "😔 Не удалось определить город или аэропорт. Попробуйте ввести IATA-код или более точное название."
        )
        return None

    if len(options) == 1:
        selected = options[0]
        await state.update_data(**{field: selected})
        await state.set_state(next_state)
        return selected

    await state.update_data(pending_location_field=field, pending_location_options=options)
    await state.set_state(choice_state)
    await message.answer(
        "Нашёл несколько подходящих вариантов. Выберите нужный город или аэропорт:",
        reply_markup=location_options_keyboard(field, options),
    )
    return None


async def _apply_location_choice(callback: CallbackQuery, state: FSMContext, *, expected_field: str) -> dict[str, str] | None:
    """Берёт выбранный пользователем вариант локации из FSMContext."""
    parts = (callback.data or "").split(":")
    if len(parts) != 3 or parts[1] != expected_field or not parts[2].isdigit():
        await callback.answer("Не удалось прочитать выбранный вариант", show_alert=True)
        return None

    data = await state.get_data()
    options = data.get("pending_location_options") or []
    index = int(parts[2])
    if index >= len(options):
        await callback.answer("Вариант устарел. Введите название заново.", show_alert=True)
        return None

    selected = options[index]
    await state.update_data(**{expected_field: selected}, pending_location_options=[], pending_location_field=None)
    await callback.answer()
    return selected



def _enrich_offer_locations(
    offers: list[dict[str, Any]],
    origin: dict[str, str],
    destination: dict[str, str],
) -> list[dict[str, Any]]:
    """Добавляет в варианты человекочитаемые названия городов и аэропортов."""
    enriched_offers: list[dict[str, Any]] = []

    for offer in offers:
        enriched_offer = {**offer}
        origin_airport = enriched_offer.get("origin_airport") or origin.get("airport_name") or origin.get("code")
        destination_airport = (
            enriched_offer.get("destination_airport") or destination.get("airport_name") or destination.get("code")
        )

        enriched_offer["origin"] = origin.get("city_name") or origin.get("name") or enriched_offer.get("origin")
        enriched_offer["destination"] = (
            destination.get("city_name") or destination.get("name") or enriched_offer.get("destination")
        )
        enriched_offer["origin_airport"] = origin_airport
        enriched_offer["destination_airport"] = destination_airport
        enriched_offers.append(enriched_offer)

    return enriched_offers

def _location_label(location: dict[str, str]) -> str:
    """Возвращает краткую подпись выбранной локации для сообщений."""
    city_name = location.get("city_name") or location.get("name") or location.get("code")
    airport_name = location.get("airport_name")
    code = location.get("code")
    if airport_name and airport_name != city_name:
        return f"{city_name} · {airport_name} ({code})"
    return f"{city_name} ({code})"


async def _ask_destination(message: Message, state: FSMContext, origin: dict[str, str]) -> None:
    """Сохраняет отправление и просит пользователя ввести пункт прилёта."""
    await state.update_data(origin=origin)
    await state.set_state(TicketSearchState.waiting_destination)
    await message.answer(f"✅ Отправление: {_location_label(origin)}\nВведите город или аэропорт прилёта:")


async def _ask_date(message: Message, state: FSMContext, destination: dict[str, str]) -> None:
    """Сохраняет прилёт и просит дату вылета."""
    data = await state.get_data()
    origin = data.get("origin") or {}
    if destination.get("code") == origin.get("code"):
        await message.answer("❌ Пункт прилёта должен отличаться от пункта вылета. Введите другое направление.")
        await state.set_state(TicketSearchState.waiting_destination)
        return

    await state.update_data(destination=destination)
    await state.set_state(TicketSearchState.waiting_date)
    await message.answer(f"✅ Прилёт: {_location_label(destination)}\nВведите дату вылета в формате YYYY-MM-DD:")


async def _ask_ticket_count(message: Message, state: FSMContext, departure_date: str) -> None:
    """Сохраняет дату и спрашивает количество билетов перед поиском."""
    await state.update_data(departure_date=departure_date)
    await state.set_state(TicketSearchState.waiting_ticket_count)
    await message.answer("Сколько билетов нужно? Введите положительное целое число.")


async def _send_offers(message: Message, state: FSMContext, ticket_count: int) -> None:
    """Выполняет асинхронный поиск и отправляет пользователю детальные варианты."""
    data = await state.get_data()
    origin = data["origin"]
    destination = data["destination"]
    departure_date = data["departure_date"]
    origin_code = origin["code"]
    destination_code = destination["code"]

    await message.answer(
        f"🔍 Ищу {ticket_count} билет(а/ов) по маршруту "
        f"{_location_label(origin)} → {_location_label(destination)} на {departure_date}..."
    )

    # Запрашиваем больше пяти, чтобы после удаления дублей сохранить минимум пять
    # разных вариантов, если API возвращает достаточно предложений.
    offers = await search_cheap_tickets(origin_code, destination_code, departure_date, ticket_count, limit=10)
    if not offers:
        await message.answer("😔 Билеты не найдены. Попробуйте другую дату или направление.")
        return

    detailed_offers = _enrich_offer_locations(offers[:10], origin, destination)
    await message.answer(
        format_ticket_offers(detailed_offers, ticket_count),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("search"))
async def search_command(message: Message, state: FSMContext) -> None:
    """Начинает FSM-сценарий поиска и запрашивает город/аэропорт отправления."""
    await state.clear()
    await state.set_state(TicketSearchState.waiting_origin)
    await message.answer("Введите город или аэропорт отправления: например MOW, Москва, Казань или Пулково.")


@router.message(TicketSearchState.waiting_origin)
async def process_origin(message: Message, state: FSMContext) -> None:
    """Определяет пункт отправления по IATA-коду или названию."""
    selected = await _resolve_location_or_ask_choice(
        message,
        state,
        message.text or "",
        field="origin",
        next_state=TicketSearchState.waiting_destination,
        choice_state=TicketSearchState.choosing_origin,
    )
    if selected:
        await _ask_destination(message, state, selected)


@router.callback_query(TicketSearchState.choosing_origin, F.data.startswith("loc:origin:"))
async def choose_origin(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор неоднозначного пункта отправления."""
    selected = await _apply_location_choice(callback, state, expected_field="origin")
    if selected:
        await _ask_destination(callback.message, state, selected)


@router.message(TicketSearchState.waiting_destination)
async def process_destination(message: Message, state: FSMContext) -> None:
    """Определяет пункт прилёта по IATA-коду или названию."""
    selected = await _resolve_location_or_ask_choice(
        message,
        state,
        message.text or "",
        field="destination",
        next_state=TicketSearchState.waiting_date,
        choice_state=TicketSearchState.choosing_destination,
    )
    if selected:
        await _ask_date(message, state, selected)


@router.callback_query(TicketSearchState.choosing_destination, F.data.startswith("loc:destination:"))
async def choose_destination(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор неоднозначного пункта прилёта."""
    selected = await _apply_location_choice(callback, state, expected_field="destination")
    if selected:
        await _ask_date(callback.message, state, selected)


@router.message(TicketSearchState.waiting_date)
async def process_date(message: Message, state: FSMContext) -> None:
    """Проверяет дату и спрашивает количество билетов."""
    departure_date = (message.text or "").strip()
    if not validate_date(departure_date):
        await message.answer(
            "❌ Неверная дата. Используйте формат YYYY-MM-DD; дата должна быть от завтра до 365 дней вперед."
        )
        return

    await _ask_ticket_count(message, state, departure_date)


@router.message(TicketSearchState.waiting_ticket_count)
async def process_ticket_count(message: Message, state: FSMContext) -> None:
    """Валидирует количество билетов и запускает поиск."""
    ticket_count = parse_positive_int(message.text)
    if ticket_count is None:
        await message.answer("❌ Введите положительное целое число, например 1, 2 или 5.")
        return

    await _send_offers(message, state, ticket_count)
    await state.clear()


@router.message(Command("popular"))
async def popular_command(message: Message, state: FSMContext) -> None:
    """Начинает FSM-сценарий популярных направлений."""
    await state.clear()
    await state.set_state(PopularDirectionState.waiting_origin)
    await message.answer("Введите город или аэропорт отправления для популярных направлений:")


@router.message(PopularDirectionState.waiting_origin)
async def process_popular_origin(message: Message, state: FSMContext) -> None:
    """Определяет пункт отправления для популярных направлений."""
    selected = await _resolve_location_or_ask_choice(
        message,
        state,
        message.text or "",
        field="origin",
        next_state=PopularDirectionState.waiting_choice,
        choice_state=PopularDirectionState.choosing_origin,
    )
    if selected:
        await _show_popular_directions(message, state, selected)


@router.callback_query(PopularDirectionState.choosing_origin, F.data.startswith("loc:origin:"))
async def choose_popular_origin(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор отправления для популярных направлений."""
    selected = await _apply_location_choice(callback, state, expected_field="origin")
    if selected:
        await _show_popular_directions(callback.message, state, selected)


async def _show_popular_directions(message: Message, state: FSMContext, origin: dict[str, str]) -> None:
    """Получает популярные направления и показывает их inline-кнопками."""
    origin_code = origin["code"]
    await state.update_data(origin=origin)
    await message.answer(f"🔥 Получаю популярные направления из {_location_label(origin)}...")
    directions = await get_popular_directions(origin_code, limit=5)

    if not directions:
        await message.answer("Не удалось найти популярные направления. Попробуйте другой город отправления.")
        await state.clear()
        return

    await state.set_state(PopularDirectionState.waiting_choice)
    await message.answer(
        "Выберите направление. После выбора я попрошу дату и количество билетов:",
        reply_markup=popular_directions_keyboard(origin_code, directions),
    )


@router.callback_query(PopularDirectionState.waiting_choice, F.data.startswith("popular:"))
async def process_popular_choice(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняет выбранное популярное направление и переводит пользователя к дате."""
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Не удалось прочитать направление", show_alert=True)
        return

    _, origin_code, destination_code = parts
    destination = {
        "code": destination_code,
        "name": destination_code,
        "city_name": destination_code,
        "airport_name": destination_code,
        "country_name": "",
        "type": "city",
    }
    await state.update_data(destination=destination)
    await state.set_state(PopularDirectionState.waiting_date)

    data = await state.get_data()
    origin = data.get("origin", {"code": origin_code, "city_name": origin_code, "airport_name": origin_code})
    await callback.message.answer(
        f"Вы выбрали маршрут {_location_label(origin)} → {destination_code}.\n"
        "Введите дату вылета в формате YYYY-MM-DD:"
    )
    await callback.answer()


@router.message(PopularDirectionState.waiting_date)
async def process_popular_date(message: Message, state: FSMContext) -> None:
    """Проверяет дату в сценарии популярных направлений и спрашивает число билетов."""
    departure_date = (message.text or "").strip()
    if not validate_date(departure_date):
        await message.answer(
            "❌ Неверная дата. Используйте формат YYYY-MM-DD; дата должна быть от завтра до 365 дней вперед."
        )
        return

    await state.update_data(departure_date=departure_date)
    await state.set_state(PopularDirectionState.waiting_ticket_count)
    await message.answer("Сколько билетов нужно? Введите положительное целое число.")


@router.message(PopularDirectionState.waiting_ticket_count)
async def process_popular_ticket_count(message: Message, state: FSMContext) -> None:
    """Валидирует количество билетов и запускает поиск из популярного направления."""
    ticket_count = parse_positive_int(message.text)
    if ticket_count is None:
        await message.answer("❌ Введите положительное целое число, например 1, 2 или 5.")
        return

    await _send_offers(message, state, ticket_count)
    await state.clear()
