"""
============================================================
Файл: states/search_states.py
Версия: 2.0.0
Дата изменения: 12.05.2026
Описание:
    FSM состояния для поиска авиабилетов.
============================================================
"""

from aiogram.fsm.state import State
from aiogram.fsm.state import StatesGroup


class TicketSearchState(StatesGroup):
    """
    FSM состояния процесса поиска билетов.
    """

    waiting_origin = State()
    waiting_destination = State()
    waiting_date = State()


class PopularDirectionState(StatesGroup):
    """
    FSM состояния популярных направлений.
    """

    waiting_origin = State()
    waiting_choice = State()