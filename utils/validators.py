"""
============================================================
Файл: utils/validators.py
Версия: 2.0.0
Дата изменения: 12.05.2026
Описание:
 Валидаторы IATA-кодов и дат.
============================================================
"""

import re
from datetime import datetime, timedelta

# Регулярное выражение для проверки формата IATA (строго 3 заглавные латинские буквы)
IATA_PATTERN = r"^[A-Z]{3}$"

# Часто используемые IATA-коды.
# Можно расширять.
KNOWN_IATA_CODES = {
    "MOW",
    "LED",
    "AER",
    "DME",
    "VKO",
    "SVO",
    "KZN",
    "OVB",
    "DXB",
    "IST",
    "BKK",
    "AYT",
    "TBS",
    "EVN",
    "JFK",
    "LAX",
    "HKT",
    "GOI",
    "DEL",
    "AMS",
    "BER",
    "PAR",
    "ROM"
}

def validate_iata(code: str) -> bool:
    """
    Проверка корректности IATA-кода.
    
    Требования:
    - Только 3 латинские буквы.
    - Код должен существовать в множестве KNOWN_IATA_CODES.
    """
    if not code or not isinstance(code, str):
        return False

    # Убираем пробелы и приводим к верхнему регистру для стандартизации
    code = code.upper().strip()

    # Проверка формата через регулярное выражение
    if not re.match(IATA_PATTERN, code):
        return False

    # Проверка наличия кода в списке известных аэропортов
    return code in KNOWN_IATA_CODES


def validate_date(date_string: str) -> bool:
    """
    Проверка даты.

    Формат:
    YYYY-MM-DD

    Ограничения:
    - не раньше завтрашнего дня
    - не позже чем через 365 дней
    """
    try:
        # Преобразуем строку в объект date
        target_date = datetime.strptime(date_string, "%Y-%m-%d").date()
        
        # Получаем текущую дату
        today = datetime.now().date()
        
        # Вычисляем границы допустимого диапазона
        tomorrow = today + timedelta(days=1)
        max_date = today + timedelta(days=365)

        # Проверяем, входит ли дата в интервал [завтра; через год]
        return tomorrow <= target_date <= max_date

    except (ValueError, TypeError):
        # ValueError — если формат строки не совпадает с маской
        # TypeError — если передана не строка
        return False