"""Целевая точка импорта резолвера локаций.

Старый модуль ``services.locations`` сохранён для совместимости обработчиков и
существующих импортов.
"""

from services.locations import (  # noqa: F401
    LOCATIONS,
    Location,
    find_locations,
    get_location_by_code,
)
