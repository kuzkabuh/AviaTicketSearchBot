"""Валидация пользовательского ввода для поиска авиабилетов."""

from datetime import datetime, timedelta
import re

# IATA-код города/аэропорта состоит из трех латинских букв. Пользователь может
# вводить код в любом регистре, но дальше приложение работает с upper-case.
IATA_PATTERN = re.compile(r"^[A-Z]{3}$")

# Часто используемые коды городов/аэропортов. Проверка по этому набору снижает
# число очевидных ошибок ввода до отправки запроса в Travelpayouts. При этом
# форматная проверка вынесена отдельно, чтобы при необходимости расширить список.
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
}


def normalize_iata(code: str | None) -> str:
    """Обрезает пробелы и приводит IATA-код к верхнему регистру."""
    return (code or "").strip().upper()


def validate_iata_format(code: str | None) -> bool:
    """Проверяет только синтаксис IATA-кода: ровно три латинские буквы."""
    return bool(IATA_PATTERN.fullmatch(normalize_iata(code)))


def validate_iata(code: str | None) -> bool:
    """
    Проверяет IATA-код по формату и списку известных популярных кодов.

    Если пользователь вводит неизвестный код, бот просит повторить ввод до
    отправки запроса в API. Список можно расширять без изменения хендлеров.
    """
    normalized_code = normalize_iata(code)
    return validate_iata_format(normalized_code) and normalized_code in KNOWN_IATA_CODES


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
