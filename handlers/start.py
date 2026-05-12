"""Стартовые команды и кнопки главного меню Telegram-бота."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards import start_search_keyboard
from states import PopularDirectionState, TicketSearchState

router = Router(name="start")


WELCOME_TEXT = (
    "👋 Добро пожаловать в AviaTicketSearchBot!\n\n"
    "Я помогу найти авиабилеты через реальные данные Aviasales/Travelpayouts.\n\n"
    "Доступные команды:\n"
    "• /search — поиск по городу, аэропорту или IATA-коду\n"
    "• /popular — популярные направления из выбранного города\n"
    "• /cancel — отменить текущий ввод"
)


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
    """Показывает приветствие и сбрасывает незавершенный FSM-сценарий."""
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=start_search_keyboard())


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    """Отправляет краткую подсказку по форматам ввода."""
    await message.answer(
        "ℹ️ Как пользоваться ботом:\n"
        "1. Введите /search.\n"
        "2. Укажите отправление: IATA-код, город или аэропорт, например MOW, Москва или Пулково.\n"
        "3. Укажите прилёт: например KZN, Казань или Сочи.\n"
        "4. Введите дату в формате YYYY-MM-DD.\n"
        "5. Укажите количество билетов положительным целым числом.\n\n"
        "Для популярных направлений используйте /popular."
    )


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    """Отменяет текущий диалог FSM, если пользователь передумал."""
    current_state = await state.get_state()
    await state.clear()

    if current_state:
        await message.answer("✅ Текущий ввод отменен. Можно начать заново: /search или /popular.")
    else:
        await message.answer("Нет активного сценария. Используйте /search или /popular.")


@router.callback_query(F.data == "menu:search")
async def menu_search(callback: CallbackQuery, state: FSMContext) -> None:
    """Запускает сценарий поиска из inline-кнопки главного меню."""
    await state.clear()
    await state.set_state(TicketSearchState.waiting_origin)
    await callback.message.answer("Введите город или аэропорт отправления: например MOW, Москва, Казань или Пулково.")
    await callback.answer()


@router.callback_query(F.data == "menu:popular")
async def menu_popular(callback: CallbackQuery, state: FSMContext) -> None:
    """Запускает сценарий популярных направлений из inline-кнопки."""
    await state.clear()
    await state.set_state(PopularDirectionState.waiting_origin)
    await callback.message.answer("Введите город или аэропорт отправления для популярных направлений:")
    await callback.answer()
