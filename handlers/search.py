"""FSM-хендлеры поиска билетов и популярных направлений."""

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from api import get_popular_directions, search_cheap_tickets
from keyboards import popular_directions_keyboard
from states import PopularDirectionState, TicketSearchState
from utils.validators import normalize_iata, validate_date, validate_iata

router = Router(name="search")


def _format_offer(offer: dict[str, Any], index: int) -> str:
    """Форматирует одно найденное предложение для Telegram-сообщения."""
    price = offer.get("price") or "—"
    airline = offer.get("airline") or "не указана"
    flight_number = offer.get("flight_number") or "-"
    transfers = offer.get("transfers")
    transfers_text = "—" if transfers is None else str(transfers)
    date = offer.get("date") or "—"
    link = offer.get("link") or "https://www.aviasales.ru"

    return (
        f"{index}. ✈️ {airline}, рейс {flight_number}\n"
        f"   📅 Дата: {date}\n"
        f"   🔁 Пересадки: {transfers_text}\n"
        f"   💰 Цена: {price} RUB\n"
        f"   🔗 <a href=\"{link}\">Открыть на Aviasales</a>"
    )


async def _send_offers(message: Message, origin: str, destination: str, departure_date: str) -> None:
    """
    Выполняет асинхронный поиск и отправляет пользователю до пяти результатов.

    Хендлер не обращается к requests и не блокирует event loop: вся сетевая
    работа вынесена в ``api.py`` и выполняется через aiohttp.
    """
    await message.answer(f"🔍 Ищу билеты {origin} → {destination} на {departure_date}...")
    offers = await search_cheap_tickets(origin, destination, departure_date)

    if not offers:
        await message.answer(
            "😔 Билеты не найдены. Попробуйте другую дату или проверьте IATA-коды маршрута."
        )
        return

    formatted_offers = [_format_offer(offer, index) for index, offer in enumerate(offers[:5], start=1)]
    await message.answer(
        "✈️ Найденные предложения:\n\n" + "\n\n".join(formatted_offers),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("search"))
async def search_command(message: Message, state: FSMContext) -> None:
    """Начинает FSM-сценарий поиска и запрашивает город отправления."""
    await state.clear()
    await state.set_state(TicketSearchState.waiting_origin)
    await message.answer("Введите IATA-код города отправления, например MOW или LED:")


@router.message(TicketSearchState.waiting_origin)
async def process_origin(message: Message, state: FSMContext) -> None:
    """Проверяет IATA отправления и сохраняет его в FSMContext."""
    origin = normalize_iata(message.text)

    if not validate_iata(origin):
        await message.answer(
            "❌ Некорректный IATA-код. Введите три латинские буквы из списка популярных кодов, "
            "например MOW, LED, AER, IST."
        )
        return

    await state.update_data(origin=origin)
    await state.set_state(TicketSearchState.waiting_destination)
    await message.answer("Введите IATA-код города назначения, например AER, IST или DXB:")


@router.message(TicketSearchState.waiting_destination)
async def process_destination(message: Message, state: FSMContext) -> None:
    """Проверяет IATA назначения и переходит к запросу даты вылета."""
    destination = normalize_iata(message.text)
    data = await state.get_data()
    origin = data.get("origin")

    if not validate_iata(destination):
        await message.answer("❌ Некорректный IATA-код назначения. Попробуйте еще раз, например AER или IST.")
        return

    if destination == origin:
        await message.answer("❌ Город назначения должен отличаться от города отправления.")
        return

    await state.update_data(destination=destination)
    await state.set_state(TicketSearchState.waiting_date)
    await message.answer("Введите дату вылета в формате YYYY-MM-DD, например 2026-06-15:")


@router.message(TicketSearchState.waiting_date)
async def process_date(message: Message, state: FSMContext) -> None:
    """Проверяет дату, вызывает API и завершает FSM-сценарий поиска."""
    departure_date = (message.text or "").strip()

    if not validate_date(departure_date):
        await message.answer(
            "❌ Неверная дата. Используйте формат YYYY-MM-DD; дата должна быть от завтра до 365 дней вперед."
        )
        return

    data = await state.get_data()
    origin = data["origin"]
    destination = data["destination"]

    await _send_offers(message, origin, destination, departure_date)
    await state.clear()


@router.message(Command("popular"))
async def popular_command(message: Message, state: FSMContext) -> None:
    """Начинает FSM-сценарий популярных направлений."""
    await state.clear()
    await state.set_state(PopularDirectionState.waiting_origin)
    await message.answer("Введите IATA-код города отправления, например MOW или LED:")


@router.message(PopularDirectionState.waiting_origin)
async def process_popular_origin(message: Message, state: FSMContext) -> None:
    """Получает популярные направления и показывает их inline-кнопками."""
    origin = normalize_iata(message.text)

    if not validate_iata(origin):
        await message.answer("❌ Некорректный IATA-код. Попробуйте MOW, LED, AER, IST или другой известный код.")
        return

    await message.answer(f"🔥 Получаю популярные направления из {origin}...")
    directions = await get_popular_directions(origin, limit=5)

    if not directions:
        await message.answer("Не удалось найти популярные направления. Попробуйте другой город отправления.")
        await state.clear()
        return

    await state.update_data(origin=origin)
    await state.set_state(PopularDirectionState.waiting_choice)
    await message.answer(
        "Выберите направление. После выбора я попрошу дату вылета и выполню поиск билетов:",
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

    await callback.message.answer(
        f"Вы выбрали маршрут {origin} → {destination}.\n"
        "Введите дату вылета в формате YYYY-MM-DD, например 2026-06-15:"
    )
    await callback.answer()
