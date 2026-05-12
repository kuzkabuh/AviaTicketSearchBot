from aiogram.fsm.state import State, StatesGroup

class SearchStates(StatesGroup):
    """Состояния для основного процесса поиска билетов."""
    origin = State()      # ожидание ввода кода отправления
    destination = State() # ожидание ввода кода назначения
    date = State()        # ожидание ввода даты

class PopularStates(StatesGroup):
    """Состояния для показа популярных направлений."""
    origin = State()      # ожидание ввода кода отправления для популярных направлений
    choose = State()      # ожидание выбора направления из списка