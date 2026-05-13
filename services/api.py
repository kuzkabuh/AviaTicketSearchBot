"""
Совместимый импорт API-клиента.

Основная реализация находится в корневом ``api.py``. Этот модуль оставлен,
чтобы старые импорты ``services.api`` не ломались.
"""

from api import (  # noqa: F401
    TravelPayoutsAPI,
    SEARCH_BY_PRICE_RANGE_ENDPOINT,
    GROUPED_PRICES_ENDPOINT,
    LATEST_PRICES_ENDPOINT,
    POPULAR_DIRECTIONS_ENDPOINT,
    PRICES_FOR_DATES_ENDPOINT,
    close_api_session,
    get_calendar_prices,
    get_popular_directions,
    search_cheap_tickets,
    travel_api,
)
