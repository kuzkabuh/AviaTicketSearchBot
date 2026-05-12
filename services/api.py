"""
Совместимый импорт API-клиента.

Основная реализация после миграции на aiogram 3.x находится в корневом
``api.py``. Этот модуль оставлен, чтобы старые импорты ``services.api`` не
ломались во время постепенного обновления проекта.
"""

from api import (  # noqa: F401
    TravelPayoutsAPI,
    close_api_session,
    get_calendar_prices,
    get_popular_directions,
    search_cheap_tickets,
    search_places,
    travel_api,
)
