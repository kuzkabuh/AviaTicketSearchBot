"""
Асинхронный клиент Travelpayouts / Aviasales API.

Публичные функции не используют заглушки: они делают реальные HTTP-запросы через
``aiohttp`` к API Travelpayouts/Aviasales и возвращают нормализованные словари,
которые удобно форматировать в Telegram-хендлерах.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import aiohttp

from config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TicketOffer:
    """Детальная нормализованная информация об одном варианте перелёта."""

    origin: str
    destination: str
    origin_airport: str
    destination_airport: str
    departure_date: str
    departure_time: str
    arrival_time: str
    duration: int | None
    transfers: int | None
    airline: str
    flight_number: str
    price: int | float | None
    currency: str
    link: str

    def as_dict(self) -> dict[str, Any]:
        """Возвращает словарь для хранения/форматирования в хендлерах."""
        return {
            "origin": self.origin,
            "destination": self.destination,
            "origin_airport": self.origin_airport,
            "destination_airport": self.destination_airport,
            "departure_date": self.departure_date,
            "date": self.departure_date,
            "departure_time": self.departure_time,
            "arrival_time": self.arrival_time,
            "duration": self.duration,
            "transfers": self.transfers,
            "airline": self.airline,
            "flight_number": self.flight_number,
            "price": self.price,
            "currency": self.currency,
            "link": self.link,
        }


class TravelPayoutsAPI:
    """Асинхронный клиент для реальных эндпоинтов Travelpayouts."""

    autocomplete_url = "https://autocomplete.travelpayouts.com/places2"

    def __init__(self) -> None:
        self.base_url = settings.base_url
        self.token = settings.travelpayouts_token
        self.currency = settings.currency
        self.marker = settings.marker
        self.timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Создаёт или переиспользует aiohttp-сессию для keep-alive соединений."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Корректно закрывает HTTP-сессию при остановке приложения."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any],
        *,
        include_token: bool = True,
        full_url: bool = False,
    ) -> dict[str, Any] | list[Any] | None:
        """
        Выполняет GET-запрос и возвращает JSON.

        В запросы к ``api.travelpayouts.com`` добавляется token, а пустые значения
        удаляются из query string. Для autocomplete используется отдельный полный
        URL без токена, потому что этот сервис работает публично.
        """
        url = endpoint if full_url else f"{self.base_url}{endpoint}"
        merged_params = {**params}
        if include_token:
            merged_params["token"] = self.token

        request_params = {key: value for key, value in merged_params.items() if value not in (None, "")}
        session = await self._get_session()

        try:
            async with session.get(url, params=request_params) as response:
                if response.status != 200:
                    body = await response.text()
                    logger.warning("Travelpayouts API error %s for %s: %s", response.status, url, body)
                    return None

                payload = await response.json(content_type=None)
                if not isinstance(payload, (dict, list)):
                    logger.warning("Unexpected JSON payload type for %s: %s", url, type(payload))
                    return None
                return payload
        except (aiohttp.ClientError, TimeoutError) as exc:
            logger.warning("HTTP request to Travelpayouts failed for %s: %s", url, exc)
            return None

    def _parse_datetime(self, value: Any) -> datetime | None:
        """Безопасно парсит datetime из строк API с timezone или без него."""
        if not isinstance(value, str) or not value:
            return None
        normalized_value = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized_value)
        except ValueError:
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(value[:19], fmt)
                except ValueError:
                    continue
        return None

    def _split_datetime(self, value: Any, fallback_date: str) -> tuple[str, str]:
        """Возвращает пару дата/время из значения ``departure_at`` или ``return_at``."""
        parsed_datetime = self._parse_datetime(value)
        if parsed_datetime:
            return parsed_datetime.date().isoformat(), parsed_datetime.strftime("%H:%M")
        return fallback_date, "не указано"

    def _build_ticket_link(self, origin: str, destination: str, departure_date: str, api_link: Any = None) -> str:
        """
        Возвращает ссылку покупки из API или формирует ссылку поиска Aviasales.

        В ответах v3 часто приходит ``link`` — относительная ссылка Aviasales. Если
        её нет, создаём URL поиска в формате ``ORIGINDDMMDESTINATION1`` и добавляем
        affiliate marker из окружения.
        """
        if isinstance(api_link, str) and api_link:
            if api_link.startswith("http"):
                return api_link
            prefix = "https://www.aviasales.ru"
            separator = "&" if "?" in api_link else "?"
            marker_query = f"{separator}{urlencode({'marker': self.marker})}" if self.marker else ""
            return f"{prefix}{api_link}{marker_query}"

        try:
            date_part = datetime.strptime(departure_date[:10], "%Y-%m-%d").strftime("%d%m")
        except ValueError:
            date_part = ""

        search_path = f"{origin}{date_part}{destination}1"
        query = urlencode({"marker": self.marker}) if self.marker else ""
        return f"https://www.aviasales.ru/search/{search_path}{'?' + query if query else ''}"

    def _extract_duration(self, raw_item: dict[str, Any]) -> int | None:
        """Извлекает продолжительность перелёта в минутах из возможных полей API."""
        for key in ("duration", "duration_to", "flight_duration"):
            value = raw_item.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        return None

    def _extract_transfers(self, raw_item: dict[str, Any]) -> int | None:
        """Извлекает количество пересадок и приводит его к int."""
        value = raw_item.get("transfers")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    def _normalize_offer(
        self,
        raw_item: dict[str, Any],
        origin: str,
        destination: str,
        fallback_date: str,
    ) -> TicketOffer:
        """
        Преобразует один элемент ответа API в единый подробный формат.

        Здесь централизованно извлекаются аэропорты, дата/время вылета и прилёта,
        длительность, пересадки, авиакомпания, рейс, цена, валюта и ссылка. Если
        конкретное поле отсутствует в ответе эндпоинта, пользователь увидит
        понятное ``не указано`` вместо ошибки хендлера.
        """
        departure_date, departure_time = self._split_datetime(raw_item.get("departure_at"), fallback_date)
        _, arrival_time = self._split_datetime(raw_item.get("return_at") or raw_item.get("arrival_at"), "")

        return TicketOffer(
            origin=str(raw_item.get("origin") or origin),
            destination=str(raw_item.get("destination") or destination),
            origin_airport=str(raw_item.get("origin_airport") or raw_item.get("origin") or origin),
            destination_airport=str(raw_item.get("destination_airport") or raw_item.get("destination") or destination),
            departure_date=departure_date,
            departure_time=departure_time,
            arrival_time=arrival_time,
            duration=self._extract_duration(raw_item),
            transfers=self._extract_transfers(raw_item),
            airline=str(raw_item.get("airline") or "не указана"),
            flight_number=str(raw_item.get("flight_number") or "-"),
            price=raw_item.get("price"),
            currency=str(raw_item.get("currency") or self.currency).upper(),
            link=self._build_ticket_link(origin, destination, departure_date, raw_item.get("link")),
        )

    def _unique_offers(self, offers: list[TicketOffer]) -> list[TicketOffer]:
        """Удаляет дубли, оставляя разные варианты перелёта для пользователя."""
        unique: list[TicketOffer] = []
        seen: set[tuple[Any, ...]] = set()

        for offer in offers:
            key = (
                offer.price,
                offer.airline,
                offer.flight_number,
                offer.departure_date,
                offer.departure_time,
                offer.transfers,
                offer.origin_airport,
                offer.destination_airport,
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(offer)

        return unique

    async def search_places(self, term: str, limit: int = 5) -> list[dict[str, Any]]:
        """Ищет города и аэропорты через autocomplete Travelpayouts."""
        params = {
            "term": term,
            "locale": "ru",
            "types[]": ["city", "airport"],
        }
        payload = await self._make_request(self.autocomplete_url, params, include_token=False, full_url=True)
        if not isinstance(payload, list):
            return []
        return [item for item in payload[:limit] if isinstance(item, dict)]

    async def search_cheap_tickets(
        self,
        origin: str,
        destination: str,
        date: str,
        ticket_count: int = 1,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Ищет варианты перелёта через ``/aviasales/v3/prices_for_dates``.

        Этот v3-эндпоинт возвращает несколько ценовых вариантов с датой/временем,
        аэропортами, авиакомпанией, рейсом, пересадками, длительностью и ссылкой.
        Если v3 временно не вернул данные, выполняется fallback на
        ``/v1/prices/cheap`` — он менее детальный, но сохраняет реальный поиск.
        """
        params = {
            "origin": origin,
            "destination": destination,
            "departure_at": date,
            "currency": self.currency,
            "sorting": "price",
            "direct": "false",
            "one_way": "true",
            "limit": max(limit, 5),
            # Некоторые версии API игнорируют adults, но параметр отражает выбор
            # пользователя и не мешает эндпоинту, если он не поддерживается.
            "adults": ticket_count,
        }
        payload = await self._make_request("/aviasales/v3/prices_for_dates", params)

        offers: list[TicketOffer] = []
        data = payload.get("data", []) if isinstance(payload, dict) else []
        if isinstance(data, list):
            for raw_item in data:
                if isinstance(raw_item, dict):
                    offers.append(self._normalize_offer(raw_item, origin, destination, date))

        if not offers:
            offers = await self._search_cheap_tickets_v1(origin, destination, date)

        offers = self._unique_offers(offers)
        offers.sort(key=lambda offer: offer.price if isinstance(offer.price, (int, float)) else float("inf"))
        return [offer.as_dict() for offer in offers[: max(limit, 5)]]

    async def _search_cheap_tickets_v1(self, origin: str, destination: str, date: str) -> list[TicketOffer]:
        """Fallback-поиск через ``/v1/prices/cheap`` с менее детальным ответом."""
        params = {
            "origin": origin,
            "destination": destination,
            "depart_date": date,
            "currency": self.currency,
        }
        payload = await self._make_request("/v1/prices/cheap", params)
        if not isinstance(payload, dict) or payload.get("success") is False:
            return []

        destination_data = payload.get("data", {}).get(destination, {})
        if not isinstance(destination_data, dict):
            return []

        raw_items: list[dict[str, Any]] = []
        if "price" in destination_data:
            raw_items.append(destination_data)
        else:
            raw_items.extend(item for item in destination_data.values() if isinstance(item, dict))

        return [self._normalize_offer(raw_item, origin, destination, date) for raw_item in raw_items]

    async def get_calendar_prices(self, origin: str, destination: str, date: str) -> list[dict[str, Any]]:
        """Получает календарь цен через ``/v2/prices/calendar``."""
        params = {
            "origin": origin,
            "destination": destination,
            "departure_at": date,
            "currency": self.currency,
        }
        payload = await self._make_request("/v2/prices/calendar", params)
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        if not isinstance(data, dict):
            return []

        offers = [
            self._normalize_offer(raw_item, origin, destination, str(flight_date))
            for flight_date, raw_item in data.items()
            if isinstance(raw_item, dict)
        ]
        offers.sort(key=lambda offer: offer.price if isinstance(offer.price, (int, float)) else float("inf"))
        return [offer.as_dict() for offer in offers]

    async def get_popular_directions(self, origin: str, limit: int = 5) -> list[dict[str, Any]]:
        """Получает популярные направления через ``/v1/city-directions``."""
        params = {
            "origin": origin,
            "currency": self.currency,
        }
        payload = await self._make_request("/v1/city-directions", params)
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        if not isinstance(data, dict):
            return []

        directions: list[dict[str, Any]] = []
        for destination, raw_item in data.items():
            if not isinstance(raw_item, dict):
                continue
            departure_date, _ = self._split_datetime(raw_item.get("departure_at"), "")
            directions.append(
                {
                    "origin": origin,
                    "destination": destination,
                    "date": departure_date,
                    "price": raw_item.get("price"),
                    "currency": str(raw_item.get("currency") or self.currency).upper(),
                    "airline": raw_item.get("airline") or "не указана",
                    "flight_number": raw_item.get("flight_number") or "-",
                    "transfers": raw_item.get("transfers"),
                    "link": self._build_ticket_link(origin, destination, departure_date, raw_item.get("link")),
                }
            )

        directions.sort(key=lambda item: item["price"] if isinstance(item.get("price"), (int, float)) else float("inf"))
        return directions[:limit]


travel_api = TravelPayoutsAPI()


async def search_places(term: str, limit: int = 5) -> list[dict[str, Any]]:
    """Функция-обёртка для поиска городов/аэропортов."""
    return await travel_api.search_places(term, limit)


async def search_cheap_tickets(
    origin: str,
    destination: str,
    date: str,
    ticket_count: int = 1,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Функция-обёртка для поиска билетов из хендлеров."""
    return await travel_api.search_cheap_tickets(origin, destination, date, ticket_count, limit)


async def get_calendar_prices(origin: str, destination: str, date: str) -> list[dict[str, Any]]:
    """Функция-обёртка для получения календаря цен."""
    return await travel_api.get_calendar_prices(origin, destination, date)


async def get_popular_directions(origin: str, limit: int = 5) -> list[dict[str, Any]]:
    """Функция-обёртка для получения популярных направлений."""
    return await travel_api.get_popular_directions(origin, limit)


async def close_api_session() -> None:
    """Закрывает глобальную aiohttp-сессию при завершении приложения."""
    await travel_api.close()
