"""
Асинхронный клиент Travelpayouts / Aviasales Data API.

Клиент использует актуальные v3-эндпоинты Data API. Важно: Data API отдаёт
кешированные цены, сформированные на основе поисков пользователей Aviasales;
это не real-time Flights Search API.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import logging
from typing import Any
from urllib.parse import urlencode

import aiohttp

from config import settings
from services.locations import get_location_by_code
from utils.validators import validate_api_date, validate_iata_format

logger = logging.getLogger(__name__)

AVIASALES_HOST = "https://www.aviasales.ru"
PRICES_FOR_DATES_ENDPOINT = "/aviasales/v3/prices_for_dates"
GROUPED_PRICES_ENDPOINT = "/aviasales/v3/grouped_prices"
LATEST_PRICES_ENDPOINT = "/aviasales/v3/get_latest_prices"
POPULAR_DIRECTIONS_ENDPOINT = "/aviasales/v3/get_popular_directions"
SEARCH_BY_PRICE_RANGE_ENDPOINT = "/aviasales/v3/search_by_price_range"
TRANSIENT_HTTP_STATUSES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class TicketOffer:
    """Нормализованное предложение билета из ответов Aviasales Data API."""

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
    expires_at: str | None = None
    source: str = "aviasales_data_api"

    def as_dict(self) -> dict[str, Any]:
        """Возвращает словарь для форматирования, подписок и сохранения."""
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
    market: str | None = None,
) -> str:
    """Формирует партнерскую ссылку на выдачу Aviasales для выбранного типа поездки."""
    date_part = _format_aviasales_date(departure_date)
    passengers_count = passengers if isinstance(passengers, int) and passengers > 0 else 1

    if trip_type == "round_trip" and return_date:
        return_part = _format_aviasales_date(return_date)
        search_path = f"{origin}{date_part}{destination}{return_part}{passengers_count}"
    else:
        search_path = f"{origin}{date_part}{destination}{passengers_count}"

    query_params = {"marker": marker, "market": market}
    query = urlencode({key: value for key, value in query_params.items() if value})
    return f"{AVIASALES_HOST}/search/{search_path}{'?' + query if query else ''}"


class TravelPayoutsAPI:
    """Асинхронный клиент актуальных эндпоинтов Aviasales Data API v3."""

    def __init__(self) -> None:
        self.base_url = settings.base_url
        self.token = settings.travelpayouts_token
        self.currency = settings.currency.lower()
        self.marker = settings.marker
        self.market = settings.market
        self.locale = settings.locale
        self.timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Создает или переиспользует aiohttp-сессию для keep-alive соединений."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers={
                    "X-Access-Token": self.token,
                    "Accept-Encoding": "gzip, deflate",
                    "Accept": "application/json",
                },
            )
        return self._session

    async def close(self) -> None:
        """Корректно закрывает HTTP-сессию при остановке приложения."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _base_params(self, **params: Any) -> dict[str, Any]:
        """Добавляет общие параметры, не включая токен в query string."""
        currency = str(params.pop("currency", self.currency)).lower()
        market = str(params.pop("market", self.market)).lower()
        merged = {
            "currency": currency,
            "market": market,
            **params,
        }
        return {key: value for key, value in merged.items() if value not in (None, "")}

    async def _make_request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Выполняет GET-запрос к Data API и возвращает JSON-словарь без утечки токена в логи."""
        url = f"{self.base_url}{endpoint}"
        session = await self._get_session()

        for attempt in range(settings.api_retry_attempts + 1):
            try:
                logger.debug("Travelpayouts request endpoint=%s params=%s attempt=%s", endpoint, params, attempt + 1)
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        body = (await response.text())[:500]
                        logger.warning("Travelpayouts API HTTP %s endpoint=%s body=%s", response.status, endpoint, body)
                        if response.status in TRANSIENT_HTTP_STATUSES and attempt < settings.api_retry_attempts:
                            await asyncio.sleep(0.5 * (attempt + 1))
                            continue
                        return None

                    try:
                        payload = await response.json(content_type=None)
                    except (aiohttp.ContentTypeError, ValueError):
                        logger.exception("Travelpayouts JSON parse failed endpoint=%s", endpoint)
                        if attempt < settings.api_retry_attempts:
                            await asyncio.sleep(0.5 * (attempt + 1))
                            continue
                        return None

                    if not isinstance(payload, dict):
                        logger.warning("Unexpected Travelpayouts payload type endpoint=%s type=%s", endpoint, type(payload))
                        return None
                    if payload.get("success") is False:
                        logger.warning("Travelpayouts API success=false endpoint=%s error=%s", endpoint, payload.get("error"))
                        return None
                    return payload
            except (aiohttp.ClientError, TimeoutError, asyncio.TimeoutError):
                logger.exception("Travelpayouts request failed endpoint=%s attempt=%s", endpoint, attempt + 1)
                if attempt < settings.api_retry_attempts:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return None
        return None

    @staticmethod
    def _validate_search_input(origin: str, destination: str | None, date: str | None = None, return_date: str | None = None) -> bool:
        """Проверяет базовые параметры перед отправкой в Data API."""
        if not validate_iata_format(origin):
            logger.warning("Invalid origin IATA before API request: %s", origin)
            return False
        if destination and not validate_iata_format(destination):
            logger.warning("Invalid destination IATA before API request: %s", destination)
            return False
        if date and not validate_api_date(date):
            logger.warning("Invalid departure date before API request: %s", date)
            return False
        if return_date and not validate_api_date(return_date):
            logger.warning("Invalid return date before API request: %s", return_date)
            return False
        return True

    @staticmethod
    def _is_expired(raw_item: dict[str, Any]) -> bool:
        """Отбрасывает цены с истекшим expires_at, если API вернул это поле."""
        expires_at = raw_item.get("expires_at")
        if not isinstance(expires_at, str) or not expires_at:
            return False
        try:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)
        return expires_dt <= datetime.now(timezone.utc)

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
                    return f"{AVIASALES_HOST}{value}"

        return build_aviasales_search_link(
            origin,
            destination,
            departure_date,
            trip_type=trip_type,
            return_date=return_date,
            marker=self.marker,
            market=getattr(self, "market", None),
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

    @staticmethod
    def _extract_price(raw_item: dict[str, Any]) -> int | float | None:
        """Извлекает цену из v3-полей price/value."""
        for field in ("price", "value"):
            value = raw_item.get(field)
            if isinstance(value, (int, float)):
                return value
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
        source: str = "aviasales_data_api",
    ) -> TicketOffer | None:
        """Преобразует один элемент ответа Data API в единый формат TicketOffer."""
        if self._is_expired(raw_item):
            logger.info("Expired Aviasales price skipped source=%s", source)
            return None

        normalized_origin = str(raw_item.get("origin") or raw_item.get("origin_code") or origin).upper()
        normalized_destination = str(raw_item.get("destination") or raw_item.get("destination_code") or destination).upper()
        departure_date = self._extract_departure_date(raw_item, fallback_date)
        airline = str(raw_item.get("airline") or raw_item.get("airline_code") or "не указана")
        flight_number = str(raw_item.get("flight_number") or raw_item.get("flight") or "-")
        transfers = self._extract_int(raw_item, "transfers", "number_of_changes", "changes")
        duration = self._extract_int(raw_item, "duration", "duration_to", "total_duration")
        departure_time = self._extract_time(raw_item, "departure_at", "departure_time", "depart_date")
        arrival_time = self._extract_time(raw_item, "return_at", "arrival_at", "arrival_time", "return_date")
        origin_city, origin_airport = self._location_parts(normalized_origin)
        destination_city, destination_airport = self._location_parts(normalized_destination)
        offer_id = str(raw_item.get("uuid") or raw_item.get("proposal_id") or raw_item.get("id") or raw_item.get("expected_price_uuid") or "")
        if not offer_id:
            offer_id = (
                f"{normalized_origin}:{normalized_destination}:{departure_date}:{departure_time}:"
                f"{arrival_time}:{airline}:{flight_number}:{transfers}:{self._extract_price(raw_item)}"
            )

        return TicketOffer(
            origin=normalized_origin,
            destination=normalized_destination,
            origin_city=origin_city,
            origin_airport=str(raw_item.get("origin_airport") or origin_airport),
            destination_city=destination_city,
            destination_airport=str(raw_item.get("destination_airport") or destination_airport),
            date=departure_date,
            departure_time=departure_time,
            arrival_time=arrival_time,
            duration=duration,
            price=self._extract_price(raw_item),
            currency=str(raw_item.get("currency") or self.currency).upper(),
            airline=airline,
            flight_number=flight_number,
            transfers=transfers,
            link=self._build_ticket_link(normalized_origin, normalized_destination, departure_date, raw_item, trip_type=trip_type, return_date=return_date),
            offer_id=offer_id,
            expires_at=raw_item.get("expires_at") if isinstance(raw_item.get("expires_at"), str) else None,
            source=source,
        )

    def _normalize_many(
        self,
        raw_items: list[dict[str, Any]],
        origin: str,
        destination: str,
        fallback_date: str,
        *,
        trip_type: str = "one_way",
        return_date: str | None = None,
        source: str,
    ) -> list[TicketOffer]:
        """Нормализует список сырых элементов, пропуская устаревшие/пустые."""
        offers: list[TicketOffer] = []
        for item in raw_items:
            offer = self._normalize_offer(item, origin, destination, fallback_date, trip_type=trip_type, return_date=return_date, source=source)
            if offer is not None:
                offers.append(offer)
        return offers

    def _deduplicate_offers(self, offers: list[TicketOffer], limit: int) -> list[TicketOffer]:
        """Удаляет одинаковые предложения и сортирует их по цене."""
        unique: dict[tuple[Any, ...], TicketOffer] = {}
        for offer in offers:
            key = (offer.price, offer.airline, offer.flight_number, offer.departure_time, offer.arrival_time, offer.transfers, offer.duration, offer.link)
            unique.setdefault(key, offer)
        result = list(unique.values())
        result.sort(key=lambda offer: offer.price if isinstance(offer.price, (int, float)) else float("inf"))
        return result[:limit]

    async def _search_prices_for_dates(
        self,
        origin: str,
        destination: str,
        date: str,
        limit: int,
        *,
        trip_type: str = "one_way",
        return_date: str | None = None,
        direct: bool = False,
        currency: str | None = None,
        market: str | None = None,
    ) -> list[TicketOffer]:
        """Ищет дешевые билеты через актуальный `/aviasales/v3/prices_for_dates`."""
        if not self._validate_search_input(origin, destination, date, return_date):
            return []

        params = self._base_params(
            origin=origin,
            destination=destination,
            departure_at=date,
            return_at=return_date if trip_type == "round_trip" else None,
            one_way="false" if trip_type == "round_trip" else "true",
            direct="true" if direct else "false",
            sorting="price",
            unique="false",
            limit=min(max(limit, 1), 1000),
            page=1,
            currency=currency,
            market=market,
        )
        payload = await self._make_request(PRICES_FOR_DATES_ENDPOINT, params)
        data = payload.get("data", []) if payload else []
        if not isinstance(data, list):
            logger.warning("Unexpected prices_for_dates data type: %s", type(data))
            return []
        return self._normalize_many(data, origin, destination, date, trip_type=trip_type, return_date=return_date, source="prices_for_dates")

    async def _search_latest_prices(
        self,
        origin: str,
        destination: str,
        date: str,
        limit: int,
        *,
        trip_type: str = "one_way",
        return_date: str | None = None,
        currency: str | None = None,
        market: str | None = None,
    ) -> list[TicketOffer]:
        """Дополняет выдачу через актуальный `/aviasales/v3/get_latest_prices`."""
        if not self._validate_search_input(origin, destination, date, return_date):
            return []

        params = self._base_params(
            origin=origin,
            destination=destination,
            beginning_of_period=date,
            period_type="day",
            group_by="dates",
            one_way="false" if trip_type == "round_trip" else "true",
            sorting="price",
            page=1,
            currency=currency,
            market=market,
        )
        payload = await self._make_request(LATEST_PRICES_ENDPOINT, params)
        data = payload.get("data", []) if payload else []
        if not isinstance(data, list):
            logger.warning("Unexpected get_latest_prices data type: %s", type(data))
            return []
        return self._normalize_many(data[:limit], origin, destination, date, trip_type=trip_type, return_date=return_date, source="get_latest_prices")

    async def _search_grouped_prices(
        self,
        origin: str,
        destination: str,
        date: str,
        *,
        trip_type: str = "one_way",
        return_date: str | None = None,
        currency: str | None = None,
        market: str | None = None,
    ) -> list[TicketOffer]:
        """Получает сгруппированные цены через актуальный `/aviasales/v3/grouped_prices`."""
        if not self._validate_search_input(origin, destination, date, return_date):
            return []

        params = self._base_params(
            origin=origin,
            destination=destination,
            group_by="departure_at",
            departure_at=date,
            return_at=return_date if trip_type == "round_trip" else None,
            direct="false",
            currency=currency,
            market=market,
        )
        payload = await self._make_request(GROUPED_PRICES_ENDPOINT, params)
        data = payload.get("data", {}) if payload else {}
        if not isinstance(data, dict):
            logger.warning("Unexpected grouped_prices data type: %s", type(data))
            return []

        raw_items = [item for item in data.values() if isinstance(item, dict)]
        return self._normalize_many(raw_items, origin, destination, date, trip_type=trip_type, return_date=return_date, source="grouped_prices")

    async def search_cheap_tickets(
        self,
        origin: str,
        destination: str,
        date: str,
        limit: int | None = None,
        *,
        trip_type: str = "one_way",
        return_date: str | None = None,
        currency: str | None = None,
        market: str | None = None,
    ) -> list[dict[str, Any]]:
        """Ищет билеты через v3 Data API и возвращает несколько релевантных вариантов."""
        effective_limit = limit or settings.ticket_results_limit
        desired_count = max(settings.min_ticket_results, effective_limit)
        offers: list[TicketOffer] = []

        offers.extend(await self._search_prices_for_dates(origin, destination, date, desired_count, trip_type=trip_type, return_date=return_date, currency=currency, market=market))
        if len(offers) < desired_count:
            offers.extend(await self._search_latest_prices(origin, destination, date, desired_count, trip_type=trip_type, return_date=return_date, currency=currency, market=market))
        if len(offers) < desired_count:
            offers.extend(await self._search_grouped_prices(origin, destination, date, trip_type=trip_type, return_date=return_date, currency=currency, market=market))

        normalized = self._deduplicate_offers(offers, effective_limit)
        logger.info("Ticket search origin=%s destination=%s date=%s trip_type=%s offers=%s", origin, destination, date, trip_type, len(normalized))
        return [offer.as_dict() for offer in normalized]

    async def get_calendar_prices(self, origin: str, destination: str, date: str) -> list[dict[str, Any]]:
        """Получает календарные цены через `/aviasales/v3/grouped_prices`."""
        offers = await self._search_grouped_prices(origin, destination, date)
        return [offer.as_dict() for offer in self._deduplicate_offers(offers, settings.ticket_results_limit)]

    async def get_popular_directions(self, origin: str, limit: int = 5) -> list[dict[str, Any]]:
        """Получает популярные направления через `/aviasales/v3/prices_for_dates` с unique=true.

        В документации этот режим указан как замена старого `/v1/city-directions`.
        """
        if not self._validate_search_input(origin, None):
            return []

        params = self._base_params(
            origin=origin,
            sorting="route",
            unique="true",
            direct="false",
            one_way="true",
            limit=min(max(limit, 1), 1000),
            page=1,
        )
        payload = await self._make_request(PRICES_FOR_DATES_ENDPOINT, params)
        data = payload.get("data", []) if payload else []
        if not isinstance(data, list):
            logger.warning("Unexpected popular directions data type: %s", type(data))
            return []

        directions = self._normalize_many([item for item in data if isinstance(item, dict)], origin, "", "", source="prices_for_dates_popular")
        normalized = self._deduplicate_offers(directions, limit)
        return [offer.as_dict() for offer in normalized]

    async def get_popular_directions_to_destination(self, destination: str, limit: int = 20) -> dict[str, Any] | None:
        """Обертка для `/aviasales/v3/get_popular_directions`, если понадобится входящий топ."""
        if not validate_iata_format(destination):
            return None
        params = self._base_params(destination=destination, locale=self.locale, limit=min(max(limit, 1), 30), page=1)
        return await self._make_request(POPULAR_DIRECTIONS_ENDPOINT, params)

    async def search_by_price_range(
        self,
        origin: str,
        destination: str,
        value_min: int,
        value_max: int,
        *,
        limit: int = 30,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """Ищет билеты через `/aviasales/v3/search_by_price_range`; сейчас используется как расширяемая сервисная обертка."""
        if not self._validate_search_input(origin, destination):
            return []
        params = self._base_params(
            origin=origin,
            destination=destination,
            value_min=max(value_min, 0),
            value_max=max(value_max, value_min),
            one_way="true",
            direct="false",
            locale=self.locale,
            limit=min(max(limit, 1), 30),
            page=max(page, 1),
        )
        payload = await self._make_request(SEARCH_BY_PRICE_RANGE_ENDPOINT, params)
        data = payload.get("data", []) if payload else []
        if not isinstance(data, list):
            return []
        offers = self._normalize_many([item for item in data if isinstance(item, dict)], origin, destination, "", source="search_by_price_range")
        return [offer.as_dict() for offer in self._deduplicate_offers(offers, limit)]


travel_api = TravelPayoutsAPI()


async def search_cheap_tickets(
    origin: str,
    destination: str,
    date: str,
    limit: int | None = None,
    *,
    trip_type: str = "one_way",
    return_date: str | None = None,
    currency: str | None = None,
    market: str | None = None,
) -> list[dict[str, Any]]:
    """Функция-обертка для поиска дешевых билетов из хендлеров."""
    return await travel_api.search_cheap_tickets(origin, destination, date, limit=limit, trip_type=trip_type, return_date=return_date, currency=currency, market=market)


async def get_calendar_prices(origin: str, destination: str, date: str) -> list[dict[str, Any]]:
    """Функция-обертка для получения календаря цен из хендлеров."""
    return await travel_api.get_calendar_prices(origin, destination, date)


async def get_popular_directions(origin: str, limit: int = 5) -> list[dict[str, Any]]:
    """Функция-обертка для получения популярных направлений из хендлеров."""
    return await travel_api.get_popular_directions(origin, limit)


async def close_api_session() -> None:
    """Закрывает глобальную aiohttp-сессию при завершении приложения."""
    await travel_api.close()
