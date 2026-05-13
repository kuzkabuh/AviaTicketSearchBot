"""Interactive Telegram calendar keyboard builders and date guards."""

from __future__ import annotations

import calendar as py_calendar
from dataclasses import dataclass
from datetime import date

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.i18n import translate

MONTHS = {
    "ru": ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
}
WEEKDAYS = {
    "ru": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
    "en": ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
}


@dataclass(slots=True, frozen=True)
class CalendarSelection:
    mode: str
    selected_date: date


def can_select_date(selected: date, *, today: date | None = None, min_date: date | None = None) -> bool:
    """Return True when selected date is not in the past and not before scenario min date."""
    current = today or date.today()
    lower_bound = max(current, min_date) if min_date else current
    return selected >= lower_bound


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    month += delta
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def build_calendar_keyboard(
    *,
    year: int,
    month: int,
    mode: str,
    language_code: str = "ru",
    today: date | None = None,
    min_date: date | None = None,
) -> InlineKeyboardMarkup:
    """Build localized month calendar; disabled days use noop callback."""
    current = today or date.today()
    builder = InlineKeyboardBuilder()
    month_name = MONTHS.get(language_code, MONTHS["ru"])[month - 1]
    builder.button(text=f"{month_name} {year}", callback_data="cal:noop")
    for weekday in WEEKDAYS.get(language_code, WEEKDAYS["ru"]):
        builder.button(text=weekday, callback_data="cal:noop")

    for week in py_calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
        for day in week:
            if day.month != month:
                builder.button(text=" ", callback_data="cal:noop")
            elif can_select_date(day, today=current, min_date=min_date):
                builder.button(text=str(day.day), callback_data=f"cal:select:{mode}:{day.isoformat()}")
            else:
                builder.button(text=f"·{day.day}", callback_data="cal:past")

    prev_year, prev_month = shift_month(year, month, -1)
    next_year, next_month = shift_month(year, month, 1)
    if date(year, month, 1) <= date(current.year, current.month, 1):
        builder.button(text=" ", callback_data="cal:noop")
    else:
        builder.button(text=translate(language_code, "calendar.prev"), callback_data=f"cal:month:{mode}:{prev_year}:{prev_month}")
    builder.button(text="•", callback_data="cal:noop")
    builder.button(text=translate(language_code, "calendar.next"), callback_data=f"cal:month:{mode}:{next_year}:{next_month}")
    builder.adjust(1, 7, 7, 7, 7, 7, 7, 3)
    return builder.as_markup()
