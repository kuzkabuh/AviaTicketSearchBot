import aiohttp
from typing import Optional, List, Dict, Any
from config import TRAVELPAYOUTS_TOKEN

BASE_URL = "http://api.travelpayouts.com"

async def get_calendar_prices(origin: str, destination: str, date: str) -> Optional[Dict[str, Any]]:
    """
    Получает данные календаря цен на месяц вперёд от указанной даты.
    Документация: https://support.travelpayouts.com/hc/ru/articles/203956163
    :param origin: IATA-код города отправления (например, LED)
    :param destination: IATA-код города назначения (например, AER)
    :param date: дата вылета в формате ГГГГ-ММ-ДД
    :return: словарь с ответом API или None при ошибке
    """
    url = f"{BASE_URL}/v2/prices/calendar"
    params = {
        "origin": origin,
        "destination": destination,
        "date": date,
        "currency": "rub",
        "token": TRAVELPAYOUTS_TOKEN,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data
            else:
                print(f"Ошибка API календаря: статус {resp.status}")
                return None

async def get_popular_directions(origin: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
    """
    Получает популярные направления из указанного города.
    Эндпоинт: /v1/prices/directions
    :param origin: IATA-код города отправления
    :param limit: максимальное количество направлений
    :return: список популярных направлений (каждый с полями destination, price и др.)
    """
    url = f"{BASE_URL}/v1/prices/directions"
    params = {
        "origin": origin,
        "currency": "rub",
        "token": TRAVELPAYOUTS_TOKEN,
        "limit": limit,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                # API возвращает {"data": [...]}
                return data.get("data", [])
            else:
                print(f"Ошибка API популярных направлений: статус {resp.status}")
                return None

async def search_cheap_tickets(origin: str, destination: str, date: str) -> Optional[List[Dict[str, Any]]]:
    """
    Поиск самых дешёвых билетов на конкретную дату.
    Эндпоинт: /v1/prices/cheap
    :param origin: IATA-код отправления
    :param destination: IATA-код назначения
    :param date: дата вылета (ГГГГ-ММ-ДД)
    :return: список предложений, каждое содержит price, airline, flight_number, link
    """
    url = f"{BASE_URL}/v1/prices/cheap"
    params = {
        "origin": origin,
        "destination": destination,
        "depart_date": date,
        "currency": "rub",
        "token": TRAVELPAYOUTS_TOKEN,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                offers = []
                # Пример структуры ответа:
                # {
                #   "success": true,
                #   "data": {
                #     "DME": {
                #       "2025-07-15": [
                #         {"price": 4500, "airline": "SU", "flight_number": 123, "ticket_id": "..."}
                #       ]
                #     }
                #   }
                # }
                if data.get("success") and "data" in data:
                    dest_data = data["data"].get(destination, {})
                    for date_key, tickets in dest_data.items():
                        for ticket in tickets:
                            # Формируем ссылку на Aviasales (пример)
                            link = f"https://aviasales.ru/search/{origin}{destination}{date_key.replace('-', '')}?ticket={ticket.get('ticket_id', '')}"
                            offers.append({
                                "price": ticket.get("price"),
                                "airline": ticket.get("airline"),
                                "flight_number": ticket.get("flight_number"),
                                "link": link,
                            })
                return offers
            else:
                print(f"Ошибка API поиска билетов: статус {resp.status}")
                return None