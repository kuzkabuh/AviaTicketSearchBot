"""
Совместимый импорт API-клиента.

Основная реализация находится в корневом ``api.py``. Этот модуль оставлен,
чтобы старые импорты ``services.api`` не ломались.
"""

from api import (  # noqa: F401
    TravelPayoutsAPI,
    close_api_session,
    get_calendar_prices,
    get_popular_directions,
    search_cheap_tickets,
    travel_api,
)
