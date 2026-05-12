"""
============================================================
Файл: services/api.py
Версия: 2.0.1
Дата изменения: 12.05.2026
Описание:
 Асинхронная работа с API Travelpayouts.
 Используется aiohttp с управлением сессией.
============================================================
"""

from typing import Any, Dict, List, Optional
import aiohttp
from config import settings

class TravelPayoutsAPI:
    """
    Класс для работы с API Travelpayouts.
    """

    def __init__(self):
        self.base_url = settings.BASE_URL
        self.token = settings.TRAVELPAYOUTS_TOKEN
        self.currency = settings.CURRENCY
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Инициализация или получение существующей сессии.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Универсальный HTTP GET запрос.
        
        Parameters:
            endpoint: endpoint API
            params: query параметры
        Returns:
            JSON ответ API или None при ошибке
        """
        url = f"{self.base_url}{endpoint}"
        session = await self._get_session()
        
        try:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status != 200:
                    print(f"Ошибка API: {response.status} | URL: {url}")
                    return None
                return await response.json()
        except Exception as e:
            print(f"Ошибка при выполнении запроса: {e}")
            return None

    async def get_calendar_prices(
        self,
        origin: str,
        destination: str,
        date: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Получение календаря цен.
        API: /v2/prices/calendar
        """
        params = {
            "origin": origin,
            "destination": destination,
            "departure_at": date,
            "currency": self.currency,
            "token": self.token,
        }
        
        response = await self._make_request(
            endpoint="/v2/prices/calendar",
            params=params
        )
        
        if not response:
            return None
        
        # Данные лежат в ключе "data"
        return response.get("data", [])

    async def get_popular_directions(
        self,
        origin: str,
        limit: int = 5
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Получение популярных направлений.
        API: /v1/prices/cheap
        """
        params = {
            "origin": origin,
            "currency": self.currency,
            "token": self.token,
            "limit": limit,
        }
        
        response = await self._make_request(
            endpoint="/v1/prices/cheap",
            params=params
        )
        
        if not response or not response.get("success"):
            return None
            
        results = []
        data = response.get("data", {})
        
        # Парсинг структуры { "DEST": { "price": ... } }
        for destination, ticket_data in data.items():
            # Обработка вложенных данных (API может возвращать данные по датам)
            if isinstance(ticket_data, dict):
                # Берем первое вхождение или данные напрямую
                results.append({
                    "destination": destination,
                    "price": ticket_data.get("price", 0),
                    "airline": ticket_data.get("airline", "N/A")
                })
        return results

    async def search_cheap_tickets(
        self,
        origin: str,
        destination: str,
        date: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Поиск дешёвых билетов.
        API: /v1/prices/cheap
        """
        params = {
            "origin": origin,
            "destination": destination,
            "depart_date": date,
            "currency": self.currency,
            "token": self.token,
        }
        
        response = await self._make_request(
            endpoint="/v1/prices/cheap",
            params=params
        )
        
        if not response or not response.get("success"):
            return None
            
        parsed_offers = []
        data = response.get("data", {})
        destination_data = data.get(destination, {})

        # Проход по датам в ответе
        for flight_date, ticket_info in destination_data.items():
            # Формирование ссылки для Aviasales
            ticket_link = (
                f"https://www.aviasales.ru/search/"
                f"{origin}{destination}"
                f"{flight_date.replace('-', '')}"
            )
            
            parsed_offers.append({
                "date": flight_date,
                "price": ticket_info.get("price"),
                "airline": ticket_info.get("airline"),
                "flight_number": ticket_info.get("flight_number"),
                "transfers": ticket_info.get("transfers"),
                "link": ticket_link,
            })

        # Сортировка по цене (по возрастанию)
        parsed_offers.sort(key=lambda x: x.get("price") or 999999999)
        
        return parsed_offers

    async def close(self):
        """Закрытие сессии при завершении работы приложения."""
        if self._session:
            await self._session.close()

# Глобальный экземпляр API для использования в приложении
travel_api = TravelPayoutsAPI()