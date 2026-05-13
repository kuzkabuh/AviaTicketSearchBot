"""
Асинхронный клиент Travelpayouts / Aviasales API.

Публичные функции делают реальные HTTP-запросы к Travelpayouts через aiohttp и
возвращают нормализованные предложения, удобные для Telegram-хендлеров,
подписок и фоновой проверки цен.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import aiohttp

from config import settings
from services.locations import get_location_by_code

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TicketOffer:
    """Нормализованное предложение билета из разных ответов Travelpayouts."""

    origin: str
    destination: str
    origin_city: str
    origin_airport: str
    destination_city: str
    destination_airport: str
    date: str
    departure_time: str
    arrival_time: str
    duration: int | None
    price: int | float | None
    currency: str
    airline: str
    flight_number: str
    transfers: int | None
    link: str
    offer_id: str

    def as_dict(self) -> dict[str, Any]:
        """Возвращает словарь для простого форматирования и сохранения."""
        return asdict(self)


def _format_aviasales_date(date_value: str | None) -> str:
    """Преобразует YYYY-MM-DD в формат даты Aviasales DDMM."""
    try:
        return datetime.strptime((date_value or "")[:10], "%Y-%m-%d").strftime("%d%m")
    except ValueError:
        return ""


def build_aviasales_search_link(
    origin: str,
    destination: str,
    departure_date: str,
    *,
    trip_type: str = "one_way",
    return_date: str | None = None,
    passengers: int = 1,
    marker: str | None = None,
) -> str:
    """Формирует партнерскую ссылку на выдачу Aviasales для выбранного типа поездки."""
    date_part = _format_aviasales_date(departure_date)
    passengers_count = passengers if isinstance(passengers, int) and passengers > 0 else 1

    if trip_type == "round_trip" and return_date:
        return_part = _format_aviasales_date(return_date)
        search_path = f"{origin}{date_part}{destination}{return_part}{passengers_count}"
    else:
        search_path = f"{origin}{date_part}{destination}{passengers_count}"

    query = urlencode({"marker": marker}) if marker else ""
    return f"https://www.aviasales.ru/search/{search_path}{'?' + query if query else ''}"


class TravelPayoutsAPI:
    """Асинхронный клиент для работы с реальными эндпоинтами Travelpayouts."""

    def __init__(self) -> None:
        self.base_url = settings.base_url
        self.token = settings.travelpayouts_token
        self.currency = settings.currency.upper()
        self.marker = settings.marker
        self.timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Создает или переиспользует aiohttp-сессию для keep-alive соединений."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Корректно закрывает HTTP-сессию при остановке бота."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _make_request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Выполняет GET-запрос к API и возвращает JSON-словарь."""
        url = f"{self.base_url}{endpoint}"
        request_params = {key: value for key, value in {**params, "token": self.token}.items() if value not in (None, "")}
        session = await self._get_session()

        try:
            async with session.get(url, params=request_params) as response:
                if response.status != 200:
                    body = await response.text()
                    logger.warning("Travelpayouts API error %s for %s: %s", response.status, endpoint, body)
                    return None
                payload = await response.json(content_type=None)
                if not isinstance(payload, dict):
                    logger.warning("Unexpected Travelpayouts payload type for %s: %s", endpoint, type(payload))
                    return None
                return payload
        except (aiohttp.ClientError, TimeoutError) as exc:
            logger.exception("HTTP request to Travelpayouts failed: %s", exc)
            return None

    def _build_ticket_link(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        raw_item: dict[str, Any] | None = None,
        *,
        trip_type: str = "one_way",
        return_date: str | None = None,
    ) -> str:
        """Формирует ссылку на билет или выдачу Aviasales для конкретного маршрута."""
        raw_item = raw_item or {}
        if trip_type != "round_trip":
            for field in ("link", "url", "deeplink"):
                value = raw_item.get(field)
                if isinstance(value, str) and value.startswith("http"):
                    return value
                if isinstance(value, str) and value.startswith("/"):
                    return f"https://www.aviasales.ru{value}"

        return build_aviasales_search_link(
            origin,
            destination,
            departure_date,
            trip_type=trip_type,
            return_date=return_date,
            marker=self.marker,
        )

    def _extract_departure_date(self, raw_item: dict[str, Any], fallback_date: str) -> str:
        """Достает дату вылета из ответа API или возвращает дату из запроса."""
        for field in ("departure_at", "depart_date", "departure_date"):
            value = raw_item.get(field)
            if isinstance(value, str) and len(value) >= 10:
                return value[:10]
        return fallback_date

    @staticmethod
    def _extract_time(raw_item: dict[str, Any], *fields: str) -> str:
        """Извлекает время HH:MM из ISO-строки или готового поля времени."""
        for field in fields:
            value = raw_item.get(field)
            if isinstance(value, str):
                if "T" in value and len(value) >= 16:
                    return value[11:16]
                if len(value) >= 5 and value[2:3] == ":":
                    return value[:5]
        return "—"

    @staticmethod
    def _extract_int(raw_item: dict[str, Any], *fields: str) -> int | None:
        """Безопасно извлекает целое число из одного из возможных полей."""
        for field in fields:
            value = raw_item.get(field)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        return None

    def _location_parts(self, code: str) -> tuple[str, str]:
        """Возвращает город и аэропорт для IATA-кода."""
        location = get_location_by_code(code)
        if not location:
            return code, code
        return location.city, location.airport

    def _normalize_offer(
        self,
        raw_item: dict[str, Any],
        origin: str,
        destination: str,
        fallback_date: str,
        *,
        trip_type: str = "one_way",
        return_date: str | None = None,
    ) -> TicketOffer:
        """Преобразует один элемент ответа API в единый формат TicketOffer."""
        departure_date = self._extract_departure_date(raw_item, fallback_date)
        airline = str(raw_item.get("airline") or raw_item.get("airline_code") or "не указана")
        flight_number = str(raw_item.get("flight_number") or raw_item.get("flight") or "-")
        transfers = self._extract_int(raw_item, "transfers", "number_of_changes", "changes")
        duration = self._extract_int(raw_item, "duration", "duration_to", "total_duration")
        departure_time = self._extract_time(raw_item, "departure_at", "departure_time")
        arrival_time = self._extract_time(raw_item, "return_at", "arrival_at", "arrival_time")
        origin_city, origin_airport = self._location_parts(origin)
        destination_city, destination_airport = self._location_parts(destination)
        offer_id = str(raw_item.get("uuid") or raw_item.get("proposal_id") or raw_item.get("id") or "")
        if not offer_id:
            offer_id = f"{origin}:{destination}:{departure_date}:{departure_time}:{arrival_time}:{airline}:{flight_number}:{transfers}:{raw_item.get('price')}"

        return TicketOffer(
            origin=origin,
            destination=destination,
            origin_city=origin_city,
            origin_airport=origin_airport,
            destination_city=destination_city,
            destination_airport=destination_airport,
            date=departure_date,
            departure_time=departure_time,
            arrival_time=arrival_time,
            duration=duration,
            price=raw_item.get("price"),
            currency=self.currency,
            airline=airline,
            flight_number=flight_number,
            transfers=transfers,
            link=self._build_ticket_link(origin, destination, departure_date, raw_item, trip_type=trip_type, return_date=return_date),
            offer_id=offer_id,
        )

    def _deduplicate_offers(self, offers: list[TicketOffer], limit: int) -> list[TicketOffer]:
        """Удаляет одинаковые предложения и сортирует их по цене."""
        unique: dict[tuple[Any, ...], TicketOffer] = {}
        for offer in offers:
            key = (offer.price, offer.airline, offer.flight_number, offer.departure_time, offer.arrival_time, offer.transfers, offer.duration)
            unique.setdefault(key, offer)
        result = list(unique.values())
        result.sort(key=lambda offer: offer.price if isinstance(offer.price, (int, float)) else float("inf"))
        return result[:limit]

    async def search_cheap_tickets(
        self,
        origin: str,
        destination: str,
        date: str,
        limit: int | None = None,
        *,
        trip_type: str = "one_way",
        return_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Ищет билеты в нескольких ценовых эндпоинтах и возвращает разные варианты."""
        limit = limit or settings.ticket_results_limit
        offers: list[TicketOffer] = []
        offers.extend(await self._search_prices_cheap(origin, destination, date, trip_type=trip_type, return_date=return_date))
        if len(offers) < max(settings.min_ticket_results, limit):
            offers.extend(await self._search_prices_latest(origin, destination, date, limit=max(settings.min_ticket_results, limit), trip_type=trip_type, return_date=return_date))
        if len(offers) < max(settings.min_ticket_results, limit):
            offers.extend(await self._search_calendar(origin, destination, date, trip_type=trip_type, return_date=return_date))

        normalized = self._deduplicate_offers(offers, limit)
        logger.info("Ticket search %s -> %s date=%s offers=%s", origin, destination, date, len(normalized))
        return [offer.as_dict() for offer in normalized]

    async def _search_prices_cheap(
        self, origin: str, destination: str, date: str, *, trip_type: str = "one_way", return_date: str | None = None
    ) -> list[TicketOffer]:
        """Парсит ``/v1/prices/cheap``."""
        params = {"origin": origin, "destination": destination, "depart_date": date, "currency": self.currency.lower()}
        payload = await self._make_request("/v1/prices/cheap", params)
        if not payload or payload.get("success") is False:
            return []

        destination_data = payload.get("data", {}).get(destination, {})
        if not isinstance(destination_data, dict):
            return []

        raw_items = [destination_data] if "price" in destination_data else [item for item in destination_data.values() if isinstance(item, dict)]
        return [self._normalize_offer(item, origin, destination, date, trip_type=trip_type, return_date=return_date) for item in raw_items]

    async def _search_prices_latest(
        self,
        origin: str,
        destination: str,
        date: str,
        limit: int,
        *,
        trip_type: str = "one_way",
        return_date: str | None = None,
    ) -> list[TicketOffer]:
        """Парсит ``/v2/prices/latest`` для получения нескольких вариантов."""
        params = {
            "origin": origin,
            "destination": destination,
            "beginning_of_period": date,
            "period_type": "day",
            "one_way": "true",
            "currency": self.currency.lower(),
            "limit": limit,
            "show_to_affiliates": "true",
        }
        payload = await self._make_request("/v2/prices/latest", params)
        data = payload.get("data", []) if payload else []
        if not isinstance(data, list):
            return []
        return [self._normalize_offer(item, origin, destination, date, trip_type=trip_type, return_date=return_date) for item in data if isinstance(item, dict)]

    async def _search_calendar(
        self, origin: str, destination: str, date: str, *, trip_type: str = "one_way", return_date: str | None = None
    ) -> list[TicketOffer]:
        """Парсит ``/v2/prices/calendar`` как резервный источник."""
        params = {"origin": origin, "destination": destination, "departure_at": date, "currency": self.currency.lower()}
        payload = await self._make_request("/v2/prices/calendar", params)
        data = payload.get("data", {}) if payload else {}
        if not isinstance(data, dict):
            return []
        return [
            self._normalize_offer(item, origin, destination, str(flight_date), trip_type=trip_type, return_date=return_date)
            for flight_date, item in data.items()
            if isinstance(item, dict)
        ]

    async def get_calendar_prices(self, origin: str, destination: str, date: str) -> list[dict[str, Any]]:
        """Получает календарь цен через ``/v2/prices/calendar``."""
        offers = await self._search_calendar(origin, destination, date)
        return [offer.as_dict() for offer in self._deduplicate_offers(offers, settings.ticket_results_limit)]

    async def get_popular_directions(self, origin: str, limit: int = 5) -> list[dict[str, Any]]:
        """Получает популярные направления из города через ``/v1/city-directions``."""
        params = {"origin": origin, "currency": self.currency.lower()}
        payload = await self._make_request("/v1/city-directions", params)
        data = payload.get("data", {}) if payload else {}
        if not isinstance(data, dict):
            return []

        directions: list[dict[str, Any]] = []
        for destination, raw_item in data.items():
            if not isinstance(raw_item, dict):
                continue
            departure_date = self._extract_departure_date(raw_item, "")
            offer = self._normalize_offer(raw_item, origin, destination, departure_date)
            directions.append(offer.as_dict())

        directions.sort(key=lambda item: item["price"] if isinstance(item.get("price"), (int, float)) else float("inf"))
        return directions[:limit]


travel_api = TravelPayoutsAPI()


async def search_cheap_tickets(
    origin: str,
    destination: str,
    date: str,
    limit: int | None = None,
    *,
    trip_type: str = "one_way",
    return_date: str | None = None,
) -> list[dict[str, Any]]:
    """Функция-обертка для поиска дешевых билетов из хендлеров."""
    return await travel_api.search_cheap_tickets(origin, destination, date, limit=limit, trip_type=trip_type, return_date=return_date)


async def get_calendar_prices(origin: str, destination: str, date: str) -> list[dict[str, Any]]:
    """Функция-обертка для получения календаря цен из хендлеров."""
    return await travel_api.get_calendar_prices(origin, destination, date)


async def get_popular_directions(origin: str, limit: int = 5) -> list[dict[str, Any]]:
    """Функция-обертка для получения популярных направлений из хендлеров."""
    return await travel_api.get_popular_directions(origin, limit)


async def close_api_session() -> None:
    """Закрывает глобальную aiohttp-сессию при завершении приложения."""
    await travel_api.close()
