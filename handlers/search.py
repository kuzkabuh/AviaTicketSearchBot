import re
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states import SearchStates, PopularStates
from api import search_cheap_tickets, get_popular_directions

router = Router()

# ----- Вспомогательные функции валидации -----
def is_valid_iata(code: str) -> bool:
    """Проверяет, что строка является IATA-кодом (3 заглавные буквы)."""
    return bool(re.fullmatch(r"[A-Z]{3}", code))

def is_valid_date(date_str: str) -> bool:
    """
    Проверяет формат даты (ГГГГ-ММ-ДД) и диапазон:
    дата должна быть не раньше завтрашнего дня и не позднее чем через год.
    """
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        tomorrow = datetime.now().date() + timedelta(days=1)
        next_year = datetime.now().date() + timedelta(days=365)
        return tomorrow <= date <= next_year
    except ValueError:
        return False

# ----- Обработчик команды /search (начало FSM) -----
@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext):
    """Запускает процесс поиска – запрашивает IATA-код отправления."""
    await state.set_state(SearchStates.origin)
    await message.answer(
        "Введите код IATA города отправления (например, LED для Санкт-Петербурга, MOW для Москвы):"
    )

# ----- Обработка города отправления -----
@router.message(SearchStates.origin)
async def process_origin(message: Message, state: FSMContext):
    """Получает и проверяет IATA отправления, переходит к запросу назначения."""
    origin = message.text.strip().upper()
    if not is_valid_iata(origin):
        await message.answer("❌ Неверный формат IATA-кода. Введите три заглавные буквы (например, LED).")
        return
    await state.update_data(origin=origin)
    await state.set_state(SearchStates.destination)
    await message.answer(
        "Теперь введите код IATA города назначения (например, AER для Сочи):"
    )

# ----- Обработка города назначения -----
@router.message(SearchStates.destination)
async def process_destination(message: Message, state: FSMContext):
    """Получает и проверяет IATA назначения, переходит к запросу даты."""
    destination = message.text.strip().upper()
    if not is_valid_iata(destination):
        await message.answer("❌ Неверный формат IATA-кода. Введите три заглавные буквы.")
        return
    await state.update_data(destination=destination)
    await state.set_state(SearchStates.date)
    await message.answer(
        "Введите дату вылета в формате ГГГГ-ММ-ДД (например, 2026-06-15).\n"
        "Дата должна быть не ранее завтрашнего дня и не позднее, чем через год."
    )

# ----- Обработка даты и выполнение поиска -----
@router.message(SearchStates.date)
async def process_date(message: Message, state: FSMContext):
    """Проверяет дату, вызывает API поиска билетов и выводит результаты."""
    date_str = message.text.strip()
    if not is_valid_date(date_str):
        await message.answer(
            "❌ Неверный формат даты или дата вне допустимого диапазона.\n"
            "Используйте ГГГГ-ММ-ДД, от завтра до года вперед."
        )
        return

    user_data = await state.get_data()
    origin = user_data["origin"]
    destination = user_data["destination"]

    await message.answer(f"🔍 Ищу билеты из {origin} в {destination} на {date_str}...")

    # Вызов асинхронного API
    offers = await search_cheap_tickets(origin, destination, date_str)

    if not offers:
        await message.answer("😔 К сожалению, билетов не найдено. Попробуйте другую дату или направление.")
        await state.clear()
        return

    # Формируем красивое сообщение с предложениями (максимум 5)
    response = f"✈️ Найдено {len(offers)} предложений:\n\n"
    for idx, offer in enumerate(offers[:5], 1):
        price = offer.get("price", "N/A")
        airline = offer.get("airline", "N/A")
        flight = offer.get("flight_number", "-")
        link = offer.get("link", "#")
        response += (
            f"{idx}. ✈️ Авиакомпания: {airline} (рейс {flight})\n"
            f"   💰 Цена: {price} руб.\n"
            f"   🔗 [Купить билет]({link})\n\n"
        )
    await message.answer(response, parse_mode="Markdown", disable_web_page_preview=True)
    await state.clear()  # Завершаем FSM

# ----- Обработчик команды /popular (популярные направления) -----
@router.message(Command("popular"))
async def cmd_popular_start(message: Message, state: FSMContext):
    """Запрашивает IATA города для получения популярных направлений."""
    await state.set_state(PopularStates.origin)
    await message.answer("Введите код IATA города отправления, чтобы узнать популярные направления:")

@router.message(PopularStates.origin)
async def process_popular_origin(message: Message, state: FSMContext):
    """Получает список популярных направлений и показывает их в виде кнопок."""
    origin = message.text.strip().upper()
    if not is_valid_iata(origin):
        await message.answer("❌ Неверный IATA-код. Введите три заглавные буквы.")
        return

    # Запрашиваем популярные направления из API
    popular = await get_popular_directions(origin)
    if not popular:
        await message.answer(f"Не удалось найти популярные направления из {origin}.")
        await state.clear()
        return

    # Строим inline-клавиатуру: каждая кнопка — направление с ценой
    builder = InlineKeyboardBuilder()
    for item in popular[:5]:  # максимум 5 направлений
        dest = item.get("destination")
        price = item.get("price")
        # В callback_data сохраняем origin и dest для последующего поиска
        builder.button(text=f"{dest} ({price} руб.)", callback_data=f"popdest_{origin}_{dest}")
    builder.adjust(1)

    await message.answer(
        f"Популярные направления из {origin}:\nВыберите одно для поиска билетов:",
        reply_markup=builder.as_markup()
    )
    # Сохраняем origin в контексте и переходим в состояние выбора
    await state.update_data(pop_origin=origin)
    await state.set_state(PopularStates.choose)

@router.callback_query(PopularStates.choose, F.data.startswith("popdest_"))
async def process_popular_choice(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор популярного направления.
    Извлекает origin и destination из callback_data, очищает состояние PopularStates
    и запускает основной FSM поиска, уже имея заполненные origin/destination.
    """
    data = callback.data.split("_")
    if len(data) != 3:
        await callback.answer("Ошибка", show_alert=True)
        return
    _, origin, destination = data

    # Очищаем состояние популярных направлений
    await state.clear()

    # Запускаем основной поиск, предзаполнив origin и destination
    # Переходим сразу к запросу даты
    await state.set_state(SearchStates.origin)
    await state.update_data(origin=origin)
    await state.set_state(SearchStates.destination)
    await state.update_data(destination=destination)
    await state.set_state(SearchStates.date)

    await callback.message.answer(
        f"Отлично! Ищем билеты из {origin} в {destination}.\n"
        "Теперь введите дату вылета в формате ГГГГ-ММ-ДД (от завтра до года вперед):"
    )
    await callback.answer()