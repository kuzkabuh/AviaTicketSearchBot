"""
FSM-состояния для сценариев поиска авиабилетов.
"""

from aiogram.fsm.state import State, StatesGroup


class TicketSearchState(StatesGroup):
    """Состояния пошагового поиска билетов."""

    waiting_origin = State()
    choosing_origin = State()
    waiting_destination = State()
    choosing_destination = State()
    waiting_trip_type = State()
    waiting_date = State()
    waiting_return_date = State()
    waiting_passengers = State()


class PopularDirectionState(StatesGroup):
    """Состояния сценария популярных направлений из выбранного города."""

    waiting_origin = State()
    choosing_origin = State()
    waiting_choice = State()


class AdminBroadcastState(StatesGroup):
    """Состояния безопасной административной рассылки."""

    waiting_text = State()
    waiting_confirmation = State()


class SubscriptionCreateState(StatesGroup):
    """Состояния сценария создания подписки."""

    waiting_target_price = State()
