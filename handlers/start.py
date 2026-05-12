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
    "Я помогу найти авиабилеты через реальные данные Aviasales/Travelpayouts, "
    "подобрать несколько вариантов и отследить изменение цены.\n\n"
    "Доступные команды:\n"
    "• /search — пошаговый поиск билетов по городу, аэропорту или IATA-коду\n"
    "• /popular — популярные направления из выбранного города\n"
    "• /subscriptions — мои подписки на цены\n"
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
        "2. Укажите пункт отправления: MOW, Москва, Шереметьево и т.п.\n"
        "3. Укажите пункт назначения: KZN, Казань, LED и т.п.\n"
        "4. Введите дату в формате YYYY-MM-DD.\n"
        "5. Укажите количество билетов целым положительным числом.\n"
        "6. Нажмите «🔔 Отслеживать цену» у нужного варианта.\n\n"
        "Подписки доступны по команде /subscriptions или кнопке «🔔 Мои подписки»."
    )


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    """Отменяет текущий диалог FSM, если пользователь передумал."""
    current_state = await state.get_state()
    await state.clear()

    if current_state:
        await message.answer("✅ Текущий ввод отменен. Можно начать заново: /search или /popular.")
    else:
        await message.answer("Нет активного сценария. Используйте /search, /popular или /subscriptions.")


@router.callback_query(F.data == "menu:search")
async def menu_search(callback: CallbackQuery, state: FSMContext) -> None:
    """Запускает сценарий поиска из inline-кнопки главного меню."""
    await state.clear()
    await state.set_state(TicketSearchState.waiting_origin)
    await callback.message.answer("Откуда вылетаете? Укажите город, аэропорт или IATA-код.")
    await callback.answer()


@router.callback_query(F.data == "menu:popular")
async def menu_popular(callback: CallbackQuery, state: FSMContext) -> None:
    """Запускает сценарий популярных направлений из inline-кнопки."""
    await state.clear()
    await state.set_state(PopularDirectionState.waiting_origin)
    await callback.message.answer("Введите город, аэропорт или IATA-код отправления для популярных направлений:")
    await callback.answer()
