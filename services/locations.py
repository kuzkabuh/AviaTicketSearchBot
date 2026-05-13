"""Поиск городов и аэропортов по IATA-коду, названию города или аэропорта."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import re

from utils.validators import normalize_iata, validate_iata_format

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Location:
    """Городской код или конкретный аэропорт, который можно использовать в поиске."""

    code: str
    city: str
    airport: str
    country: str = ""
    is_city: bool = False

    @property
    def display_name(self) -> str:
        """Человекочитаемое название для сообщений и inline-кнопок."""
        suffix = "все аэропорты" if self.is_city else self.airport
        return f"{self.city} — {suffix} ({self.code})"

    def as_dict(self) -> dict[str, str | bool]:
        """Сериализует объект для FSMContext и подписок."""
        return asdict(self)


LOCATIONS: tuple[Location, ...] = (
    Location("MOW", "Москва", "все аэропорты", "Россия", True),
    Location("SVO", "Москва", "Шереметьево", "Россия"),
    Location("DME", "Москва", "Домодедово", "Россия"),
    Location("VKO", "Москва", "Внуково", "Россия"),
    Location("ZIA", "Москва", "Жуковский", "Россия"),
    Location("KZN", "Казань", "Казань", "Россия", True),
    Location("LED", "Санкт-Петербург", "Пулково", "Россия", True),
    Location("AER", "Сочи", "Сочи", "Россия", True),
    Location("SIP", "Симферополь", "Симферополь", "Россия", True),
    Location("OVB", "Новосибирск", "Толмачёво", "Россия", True),
    Location("IST", "Стамбул", "Istanbul Airport", "Турция", True),
    Location("AYT", "Анталья", "Анталья", "Турция", True),
    Location("DXB", "Дубай", "Dubai International", "ОАЭ", True),
    Location("BKK", "Бангкок", "Суварнабхуми", "Таиланд", True),
    Location("HKT", "Пхукет", "Пхукет", "Таиланд", True),
    Location("EVN", "Ереван", "Звартноц", "Армения", True),
    Location("TBS", "Тбилиси", "Шота Руставели", "Грузия", True),
    Location("AMS", "Амстердам", "Схипхол", "Нидерланды", True),
    Location("LON", "London", "all airports", "United Kingdom", True),
    Location("BER", "Берлин", "Бранденбург", "Германия", True),
    Location("PAR", "Париж", "все аэропорты", "Франция", True),
    Location("ROM", "Рим", "все аэропорты", "Италия", True),
    Location("JFK", "Нью-Йорк", "John F. Kennedy", "США"),
    Location("LAX", "Лос-Анджелес", "Los Angeles International", "США"),
    Location("GOI", "Гоа", "Даболим", "Индия", True),
    Location("DEL", "Дели", "Indira Gandhi", "Индия", True),
)


def _normalize_text(value: str) -> str:
    """Готовит пользовательский текст к нестрогому поиску."""
    return re.sub(r"\s+", " ", value.casefold().replace("ё", "е")).strip()


def get_location_by_code(code: str | None) -> Location | None:
    """Возвращает локацию по IATA-коду, если она есть в локальном справочнике."""
    normalized = normalize_iata(code)
    for location in LOCATIONS:
        if location.code == normalized:
            return location
    if validate_iata_format(normalized):
        logger.info("Unknown but syntactically valid IATA code accepted: %s", normalized)
        return Location(normalized, normalized, normalized, "", True)
    return None


def find_locations(query: str | None, limit: int = 8) -> list[Location]:
    """Ищет подходящие города/аэропорты по коду, названию города или аэропорта."""
    raw_query = (query or "").strip()
    if not raw_query:
        return []

    normalized_code = normalize_iata(raw_query)
    if validate_iata_format(normalized_code):
        location = get_location_by_code(normalized_code)
        return [location] if location else []

    aliases = {"москвы": "москва", "питера": "санкт-петербург", "лондона": "london", "казани": "казань"}
    needle = aliases.get(_normalize_text(raw_query), _normalize_text(raw_query))
    exact: list[Location] = []
    partial: list[Location] = []

    for location in LOCATIONS:
        city = _normalize_text(location.city)
        airport = _normalize_text(location.airport)
        code = location.code.casefold()
        if needle in {city, airport, code}:
            exact.append(location)
        elif needle in city or needle in airport:
            partial.append(location)

    results = exact + [location for location in partial if location not in exact]
    logger.info("Location search query=%r results=%s", raw_query, [item.code for item in results[:limit]])
    return results[:limit]
