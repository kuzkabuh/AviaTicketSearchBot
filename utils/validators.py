"""Валидация и нормализация пользовательского ввода для поиска билетов."""

from datetime import datetime, timedelta
import re

# IATA-код города/аэропорта состоит из трех латинских букв. Пользователь может
# вводить код в любом регистре, но дальше приложение работает с upper-case.
IATA_PATTERN = re.compile(r"^[A-Z]{3}$")

# Названия городов и аэропортов могут содержать кириллицу/латиницу, пробелы,
# дефисы и точки. Ограничиваем только очевидно ошибочный ввод.
LOCATION_TEXT_PATTERN = re.compile(r"^[A-Za-zА-Яа-яЁё0-9 .\-()]+$")

# Популярные коды оставлены для быстрой локальной проверки и fallback-поиска.
KNOWN_IATA_CODES = {
    "AER",
    "AMS",
    "AYT",
    "BER",
    "BKK",
    "DEL",
    "DME",
    "DXB",
    "EVN",
    "GOI",
    "HKT",
    "IST",
    "JFK",
    "KZN",
    "LAX",
    "LED",
    "MOW",
    "OVB",
    "PAR",
    "ROM",
    "SIP",
    "SVO",
    "TBS",
    "VKO",
    "SVX",
    "PEE",
    "UFA",
    "ROV",
    "KRR",
}


def normalize_iata(code: str | None) -> str:
    """Обрезает пробелы и приводит IATA-код к верхнему регистру."""
    return (code or "").strip().upper()


def normalize_location_query(query: str | None) -> str:
    """Нормализует название города/аэропорта без потери исходного языка."""
    return " ".join((query or "").strip().split())


def validate_iata_format(code: str | None) -> bool:
    """Проверяет только синтаксис IATA-кода: ровно три латинские буквы."""
    return bool(IATA_PATTERN.fullmatch(normalize_iata(code)))


def validate_iata(code: str | None) -> bool:
    """
    Проверяет IATA-код по формату и локальному списку известных кодов.

    Основной сценарий теперь использует поиск локаций по API/словарю, поэтому
    эта функция нужна как быстрый фильтр для явного ввода кода аэропорта/города.
    """
    normalized_code = normalize_iata(code)
    return validate_iata_format(normalized_code) and normalized_code in KNOWN_IATA_CODES


def validate_location_query(query: str | None) -> bool:
    """Проверяет, что строка похожа на название города, аэропорта или IATA-код."""
    normalized_query = normalize_location_query(query)
    if len(normalized_query) < 2 or len(normalized_query) > 80:
        return False
    return bool(LOCATION_TEXT_PATTERN.fullmatch(normalized_query))


def validate_date(date_string: str | None) -> bool:
    """
    Проверяет дату вылета в формате YYYY-MM-DD.

    Допускаются даты от завтра до 365 дней вперед: прошедшие даты и слишком
    дальние даты не отправляются в API, потому что они с высокой вероятностью
    вернут пустой или некорректный результат.
    """
    try:
        target_date = datetime.strptime((date_string or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return False

    today = datetime.now().date()
    return today + timedelta(days=1) <= target_date <= today + timedelta(days=365)


def parse_positive_int(value: str | None) -> int | None:
    """Возвращает положительное целое число или None при некорректном вводе."""
    normalized_value = (value or "").strip()
    if not normalized_value.isdigit():
        return None

    parsed_value = int(normalized_value)
    if parsed_value <= 0:
        return None
    return parsed_value
