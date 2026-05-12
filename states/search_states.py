"""
FSM-состояния для сценариев поиска авиабилетов.

В aiogram 3.x вместо telebot.register_next_step_handler используется FSM:
каждый ответ пользователя обрабатывается только в ожидаемом состоянии, а
промежуточные данные маршрута сохраняются в FSMContext.
"""

from aiogram.fsm.state import State, StatesGroup


class TicketSearchState(StatesGroup):
    """Состояния пошагового поиска билетов."""

    waiting_origin = State()
    choosing_origin = State()
    waiting_destination = State()
    choosing_destination = State()
    waiting_date = State()
    waiting_ticket_count = State()


class PopularDirectionState(StatesGroup):
    """Состояния сценария популярных направлений из выбранного города."""

    waiting_origin = State()
    choosing_origin = State()
    waiting_choice = State()
    waiting_date = State()
    waiting_ticket_count = State()
