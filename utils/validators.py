"""Валидация пользовательского ввода для поиска авиабилетов."""

from datetime import datetime, timedelta
import re

IATA_PATTERN = re.compile(r"^[A-Z]{3}$")

KNOWN_IATA_CODES = {
    "AER", "AMS", "AYT", "BER", "BKK", "DEL", "DME", "DXB", "EVN", "GOI", "HKT", "IST",
    "JFK", "KZN", "LAX", "LED", "MOW", "OVB", "PAR", "ROM", "SIP", "SVO", "TBS", "VKO", "ZIA",
}


def normalize_iata(code: str | None) -> str:
    """Обрезает пробелы и приводит IATA-код к верхнему регистру."""
    return (code or "").strip().upper()


def validate_iata_format(code: str | None) -> bool:
    """Проверяет только синтаксис IATA-кода: ровно три латинские буквы."""
    return bool(IATA_PATTERN.fullmatch(normalize_iata(code)))


def validate_iata(code: str | None) -> bool:
    """Проверяет IATA-код по формату и списку известных популярных кодов."""
    normalized_code = normalize_iata(code)
    return validate_iata_format(normalized_code) and normalized_code in KNOWN_IATA_CODES


def validate_date(date_string: str | None) -> bool:
    """Проверяет дату вылета в формате YYYY-MM-DD: от завтра до 365 дней вперед."""
    try:
        target_date = datetime.strptime((date_string or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return False

    today = datetime.now().date()
    return today + timedelta(days=1) <= target_date <= today + timedelta(days=365)


def parse_positive_int(value: str | None) -> int | None:
    """Возвращает положительное целое число или None для некорректного ввода."""
    text = (value or "").strip()
    if not re.fullmatch(r"[1-9]\d*", text):
        return None
    return int(text)
