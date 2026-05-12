"""Поиск городов и аэропортов по IATA-коду или обычному названию."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from api import search_places
from utils.validators import normalize_iata, normalize_location_query, validate_iata_format



@dataclass(frozen=True)
class LocationOption:
    """Нормализованный город или аэропорт, который можно использовать в поиске."""

    code: str
    name: str
    city_name: str
    airport_name: str
    country_name: str
    type: str

    @property
    def title(self) -> str:
        """Человекочитаемое название для сообщений и кнопок."""
        parts = [self.city_name or self.name]
        if self.airport_name and self.airport_name not in parts:
            parts.append(self.airport_name)
        if self.country_name:
            parts.append(self.country_name)
        return " · ".join(part for part in parts if part)

    def as_dict(self) -> dict[str, str]:
        """Сериализует объект для хранения в FSMContext."""
        return asdict(self)


# Локальный индекс нужен для мгновенного ответа по самым популярным русским
# названиям и как fallback, если autocomplete Travelpayouts временно недоступен.
LOCAL_LOCATIONS = [
    LocationOption("MOW", "Москва", "Москва", "Все аэропорты Москвы", "Россия", "city"),
    LocationOption("SVO", "Шереметьево", "Москва", "Шереметьево", "Россия", "airport"),
    LocationOption("DME", "Домодедово", "Москва", "Домодедово", "Россия", "airport"),
    LocationOption("VKO", "Внуково", "Москва", "Внуково", "Россия", "airport"),
    LocationOption("KZN", "Казань", "Казань", "Казань", "Россия", "city"),
    LocationOption("LED", "Санкт-Петербург", "Санкт-Петербург", "Пулково", "Россия", "city"),
    LocationOption("LED", "Пулково", "Санкт-Петербург", "Пулково", "Россия", "airport"),
    LocationOption("AER", "Сочи", "Сочи", "Адлер/Сочи", "Россия", "city"),
    LocationOption("SVX", "Екатеринбург", "Екатеринбург", "Кольцово", "Россия", "city"),
    LocationOption("SVX", "Кольцово", "Екатеринбург", "Кольцово", "Россия", "airport"),
    LocationOption("OVB", "Новосибирск", "Новосибирск", "Толмачёво", "Россия", "city"),
    LocationOption("PEE", "Пермь", "Пермь", "Большое Савино", "Россия", "city"),
    LocationOption("UFA", "Уфа", "Уфа", "Уфа", "Россия", "city"),
    LocationOption("ROV", "Ростов-на-Дону", "Ростов-на-Дону", "Платов", "Россия", "city"),
    LocationOption("KRR", "Краснодар", "Краснодар", "Пашковский", "Россия", "city"),
]


ALIASES = {
    "мск": "москва",
    "спб": "санкт-петербург",
    "питер": "санкт-петербург",
    "петербург": "санкт-петербург",
    "адлер": "сочи",
}


def _normalize_search_text(value: str) -> str:
    """Готовит строку к нестрогому поиску по локальному индексу."""
    normalized = normalize_location_query(value).casefold().replace("ё", "е")
    return ALIASES.get(normalized, normalized)


def _option_from_api_item(item: dict[str, Any]) -> LocationOption | None:
    """Преобразует один объект autocomplete Travelpayouts в LocationOption."""
    code = normalize_iata(item.get("code") or item.get("iata"))
    if not validate_iata_format(code):
        return None

    name = str(item.get("name") or item.get("name_translations", {}).get("ru") or code)
    city_name = str(item.get("city_name") or item.get("city_name_translations", {}).get("ru") or name)
    airport_name = str(item.get("airport_name") or item.get("name") or "")
    country_name = str(item.get("country_name") or item.get("country_name_translations", {}).get("ru") or "")
    location_type = str(item.get("type") or "location")

    return LocationOption(
        code=code,
        name=name,
        city_name=city_name,
        airport_name=airport_name,
        country_name=country_name,
        type=location_type,
    )


def _deduplicate(options: list[LocationOption]) -> list[LocationOption]:
    """Удаляет полные дубли, сохраняя порядок выдачи API/fallback."""
    seen: set[tuple[str, str, str]] = set()
    unique_options: list[LocationOption] = []

    for option in options:
        key = (option.code, option.city_name.casefold(), option.airport_name.casefold())
        if key in seen:
            continue
        seen.add(key)
        unique_options.append(option)

    return unique_options


def _search_local_locations(query: str) -> list[LocationOption]:
    """Ищет совпадения по локальному списку городов/аэропортов и алиасов."""
    normalized_query = _normalize_search_text(query)
    iata_query = normalize_iata(query)

    matches: list[LocationOption] = []
    for option in LOCAL_LOCATIONS:
        searchable_values = {
            option.code.casefold(),
            _normalize_search_text(option.name),
            _normalize_search_text(option.city_name),
            _normalize_search_text(option.airport_name),
        }
        if iata_query == option.code or any(normalized_query in value for value in searchable_values):
            matches.append(option)

    return matches


async def find_locations(query: str, limit: int = 5) -> list[dict[str, str]]:
    """
    Возвращает список подходящих городов/аэропортов для пользовательского ввода.

    Сначала выполняется реальный запрос к autocomplete Travelpayouts, чтобы
    поддерживать широкий список городов и аэропортов. Затем добавляется локальный
    fallback для популярных русских названий и случаев временной ошибки API.
    """
    normalized_query = normalize_location_query(query)
    options: list[LocationOption] = []

    api_items = await search_places(normalized_query, limit=limit)
    for item in api_items:
        option = _option_from_api_item(item)
        if option:
            options.append(option)

    options.extend(_search_local_locations(normalized_query))
    unique_options = _deduplicate(options)
    return [option.as_dict() for option in unique_options[:limit]]
