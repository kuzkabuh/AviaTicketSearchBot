from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from typing import List, Dict, Any

def popular_directions_keyboard(directions: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Создаёт inline-клавиатуру из списка популярных направлений.
    Каждая кнопка содержит название города и цену, callback_data = "popdest_<origin>_<dest>".
    """
    builder = InlineKeyboardBuilder()
    for item in directions:
        dest = item.get("destination")
        price = item.get("price")
        # В callback_data будем кодировать город отправления и назначения
        # Для корректной работы добавим поле origin, но оно будет известно только в момент вызова.
        # Здесь мы не знаем origin, поэтому клавиатура будет строиться в обработчике.
        # Этот файл оставляем для возможных общих утилит.
        pass

# Так как построение конкретной клавиатуры зависит от origin, реализуем её прямо в хендлере.
# Приведённый выше код – просто пример. Фактически используем InlineKeyboardBuilder в search.py.