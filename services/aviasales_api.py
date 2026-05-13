"""Основная точка импорта клиента Aviasales Data API для новых модулей.

Реализация пока живёт в корневом ``api.py`` для обратной совместимости со
старыми импортами проекта; этот модуль фиксирует целевую архитектурную границу
``services/aviasales_api.py`` без ломки существующего кода.
"""

from api import (  # noqa: F401
    GROUPED_PRICES_ENDPOINT,
    LATEST_PRICES_ENDPOINT,
    POPULAR_DIRECTIONS_ENDPOINT,
    PRICES_FOR_DATES_ENDPOINT,
    SEARCH_BY_PRICE_RANGE_ENDPOINT,
    TravelPayoutsAPI,
    build_aviasales_search_link,
    close_api_session,
    get_calendar_prices,
    get_popular_directions,
    search_cheap_tickets,
    travel_api,
)
