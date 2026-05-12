import requests
from config import TRAVEL_API_TOKEN, API_URL

def get_tickets(origin, destination, departure_at=None, return_at=None):
    """
    Функция для запроса билетов через API Travelpayouts.
    """
    params = {
        "origin": origin.upper(),       # Код города отправления (например, MOW)
        "destination": destination.upper(), # Код города назначения
        "departure_at": departure_at,
        "return_at": return_at,
        "unique": "false",
        "sorting": "price",
        "direct": "false",
        "currency": "rub",
        "limit": 5,                     # Ограничиваем выдачу 5 билетами
        "token": TRAVEL_API_TOKEN
    }

    try:
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()  # Вызовет ошибку при кодах 4xx/5xx
        data = response.json()

        # Проверяем наличие ключа 'data' и что он не пуст
        if "data" in data and data["data"]:
            return data["data"]
        return []
    except Exception as e:
        print(f"Ошибка при запросе к API: {e}")
        return None