"""
Асинхронный клиент Travelpayouts / Aviasales API.

В модуле нет заглушек: все публичные функции делают реальные HTTP-запросы к
эндпоинтам Travelpayouts через aiohttp и возвращают нормализованные данные,
удобные для Telegram-хендлеров.
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
    """Нормализованное предложение билета из разных ответов Travelpayouts."""

    origin: str
    destination: str
    date: str
    price: int | float | None
    airline: str
    flight_number: str
    transfers: int | None
    link: str

    def as_dict(self) -> dict[str, Any]:
        """Возвращает словарь для простого форматирования в хендлерах."""
        return {
            "origin": self.origin,
            "destination": self.destination,
            "date": self.date,
            "price": self.price,
            "airline": self.airline,
            "flight_number": self.flight_number,
            "transfers": self.transfers,
            "link": self.link,
        }


class TravelPayoutsAPI:
    """Асинхронный клиент для работы с реальными эндпоинтами Travelpayouts."""

    def __init__(self) -> None:
        self.base_url = settings.base_url
        self.token = settings.travelpayouts_token
        self.currency = settings.currency
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
        """
        Выполняет GET-запрос к API и возвращает JSON-словарь.

        В каждый запрос добавляется токен Travelpayouts. Параметры с пустыми
        значениями удаляются, чтобы API не получал ``None`` или пустые строки.
        Такой подход важен для эндпоинтов цен: необязательные фильтры должны
        отсутствовать в query string, а не передаваться пустыми.
        """
        url = f"{self.base_url}{endpoint}"
        request_params = {
            key: value
            for key, value in {**params, "token": self.token}.items()
            if value not in (None, "")
        }

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

    def _build_ticket_link(self, origin: str, destination: str, departure_date: str) -> str:
        """
        Формирует ссылку на выдачу Aviasales для конкретного маршрута.

        Aviasales использует формат ``ORIGINDDMMDESTINATION1`` для поиска в одну
        сторону. Например, MOW -> AER на 2026-06-15 превращается в
        ``MOW1506AER1``. Marker добавляется query-параметром, если он задан в .env.
        """
        try:
            date_part = datetime.strptime(departure_date[:10], "%Y-%m-%d").strftime("%d%m")
        except ValueError:
            # Если API вернул нестандартную дату, оставляем безопасную ссылку на
            # общий поиск маршрута, но не ломаем показ результата пользователю.
            date_part = ""

        search_path = f"{origin}{date_part}{destination}1"
        query = urlencode({"marker": self.marker}) if self.marker else ""
        return f"https://www.aviasales.ru/search/{search_path}{'?' + query if query else ''}"

    def _extract_departure_date(self, raw_item: dict[str, Any], fallback_date: str) -> str:
        """Достает дату вылета из ответа API или возвращает дату из запроса."""
        departure_at = raw_item.get("departure_at")
        if isinstance(departure_at, str) and len(departure_at) >= 10:
            return departure_at[:10]
        return fallback_date

    def _normalize_offer(
        self,
        raw_item: dict[str, Any],
        origin: str,
        destination: str,
        fallback_date: str,
    ) -> TicketOffer:
        """
        Преобразует один элемент ответа API в единый формат TicketOffer.

        Разные эндпоинты Travelpayouts могут возвращать похожие поля в немного
        разной структуре. Здесь централизованно извлекаются цена, авиакомпания,
        номер рейса, количество пересадок и дата, а затем строится ссылка на
        покупку/поиск билета на Aviasales.
        """
        departure_date = self._extract_departure_date(raw_item, fallback_date)
        airline = str(raw_item.get("airline") or "не указана")
        flight_number = str(raw_item.get("flight_number") or "-")

        transfers: int | None = None
        raw_transfers = raw_item.get("transfers")
        if isinstance(raw_transfers, int):
            transfers = raw_transfers
        elif isinstance(raw_transfers, str) and raw_transfers.isdigit():
            transfers = int(raw_transfers)

        return TicketOffer(
            origin=origin,
            destination=destination,
            date=departure_date,
            price=raw_item.get("price"),
            airline=airline,
            flight_number=flight_number,
            transfers=transfers,
            link=self._build_ticket_link(origin, destination, departure_date),
        )

    async def search_cheap_tickets(self, origin: str, destination: str, date: str) -> list[dict[str, Any]]:
        """
        Ищет дешевые билеты через реальный эндпоинт ``/v1/prices/cheap``.

        Для конкретной даты Travelpayouts возвращает данные по направлению в
        структуре ``data -> DESTINATION -> transfer_key -> ticket_info``. Поэтому
        парсер проходит по всем вложенным предложениям, нормализует каждое и
        сортирует результат по цене.
        """
        params = {
            "origin": origin,
            "destination": destination,
            "depart_date": date,
            "currency": self.currency,
        }
        payload = await self._make_request("/v1/prices/cheap", params)

        if not payload or payload.get("success") is False:
            return []

        destination_data = payload.get("data", {}).get(destination, {})
        if not isinstance(destination_data, dict):
            return []

        offers: list[TicketOffer] = []

        # В большинстве ответов /v1/prices/cheap предложения лежат во вложенных
        # ключах с количеством пересадок: {"0": {...}, "1": {...}}. На случай
        # если API вернет один билет сразу в data[destination], поддерживаем и
        # прямую структуру с полем price.
        if "price" in destination_data:
            offers.append(self._normalize_offer(destination_data, origin, destination, date))
        else:
            for raw_item in destination_data.values():
                if isinstance(raw_item, dict):
                    offers.append(self._normalize_offer(raw_item, origin, destination, date))

        offers.sort(key=lambda offer: offer.price if isinstance(offer.price, (int, float)) else float("inf"))
        return [offer.as_dict() for offer in offers]

    async def get_calendar_prices(self, origin: str, destination: str, date: str) -> list[dict[str, Any]]:
        """
        Получает календарь цен через ``/v2/prices/calendar``.

        Эндпоинт возвращает словарь в ключе ``data``. Ключи обычно являются
        датами, а значения содержат цену и дополнительные параметры рейса. Для
        хендлеров возвращается список нормализованных предложений.
        """
        params = {
            "origin": origin,
            "destination": destination,
            "departure_at": date,
            "currency": self.currency,
        }
        payload = await self._make_request("/v2/prices/calendar", params)

        data = payload.get("data", {}) if payload else {}
        if not isinstance(data, dict):
            return []

        offers: list[TicketOffer] = []
        for flight_date, raw_item in data.items():
            if isinstance(raw_item, dict):
                offers.append(self._normalize_offer(raw_item, origin, destination, str(flight_date)))

        offers.sort(key=lambda offer: offer.price if isinstance(offer.price, (int, float)) else float("inf"))
        return [offer.as_dict() for offer in offers]

    async def get_popular_directions(self, origin: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Получает популярные направления из города через ``/v1/city-directions``.

        Ответ имеет вид ``data -> DESTINATION -> ticket_info``. Из каждого
        направления извлекаются город назначения, цена, авиакомпания, дата и
        ссылка на Aviasales. ``limit`` применяется после сортировки по цене.
        """
        params = {
            "origin": origin,
            "currency": self.currency,
        }
        payload = await self._make_request("/v1/city-directions", params)

        data = payload.get("data", {}) if payload else {}
        if not isinstance(data, dict):
            return []

        directions: list[dict[str, Any]] = []
        for destination, raw_item in data.items():
            if not isinstance(raw_item, dict):
                continue

            departure_date = self._extract_departure_date(raw_item, "")
            directions.append(
                {
                    "origin": origin,
                    "destination": destination,
                    "date": departure_date,
                    "price": raw_item.get("price"),
                    "airline": raw_item.get("airline") or "не указана",
                    "flight_number": raw_item.get("flight_number") or "-",
                    "transfers": raw_item.get("transfers"),
                    "link": self._build_ticket_link(origin, destination, departure_date),
                }
            )

        directions.sort(key=lambda item: item["price"] if isinstance(item.get("price"), (int, float)) else float("inf"))
        return directions[:limit]


travel_api = TravelPayoutsAPI()


async def search_cheap_tickets(origin: str, destination: str, date: str) -> list[dict[str, Any]]:
    """Функция-обертка для поиска дешевых билетов из хендлеров."""
    return await travel_api.search_cheap_tickets(origin, destination, date)


async def get_calendar_prices(origin: str, destination: str, date: str) -> list[dict[str, Any]]:
    """Функция-обертка для получения календаря цен из хендлеров."""
    return await travel_api.get_calendar_prices(origin, destination, date)


async def get_popular_directions(origin: str, limit: int = 5) -> list[dict[str, Any]]:
    """Функция-обертка для получения популярных направлений из хендлеров."""
    return await travel_api.get_popular_directions(origin, limit)


async def close_api_session() -> None:
    """Закрывает глобальную aiohttp-сессию при завершении приложения."""
    await travel_api.close()
