"""Rule-based RU/EN natural-language flight-search parser."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from services.search_models import PassengerCounts

RU_MONTHS = {
    "января": 1, "январь": 1, "февраля": 2, "февраль": 2, "марта": 3, "март": 3,
    "апреля": 4, "апрель": 4, "мая": 5, "май": 5, "июня": 6, "июнь": 6,
    "июля": 7, "июль": 7, "августа": 8, "август": 8, "сентября": 9, "сентябрь": 9,
    "октября": 10, "октябрь": 10, "ноября": 11, "ноябрь": 11, "декабря": 12, "декабрь": 12,
}
EN_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
MONTHS_PATTERN = "|".join(sorted([*RU_MONTHS, *EN_MONTHS], key=len, reverse=True))
DATE_RE = re.compile(rf"(?P<day>\d{{1,2}})\s+(?P<month>{MONTHS_PATTERN})(?:\s+(?P<year>20\d{{2}}))?|(?P<month2>{MONTHS_PATTERN})\s+(?P<day2>\d{{1,2}})(?:,?\s+(?P<year2>20\d{{2}}))?", re.I)


@dataclass(slots=True)
class NaturalSearchParseResult:
    origin_text: str | None = None
    destination_text: str | None = None
    departure_date: str | None = None
    return_date: str | None = None
    trip_type: str = "one_way"
    passengers: PassengerCounts = field(default_factory=PassengerCounts)
    confidence: float = 0.0
    missing: list[str] = field(default_factory=list)
    unrecognized: list[str] = field(default_factory=list)


def _future_date(day: int, month: int, year: int | None, today: date) -> date | None:
    try:
        candidate = date(year or today.year, month, day)
    except ValueError:
        return None
    if year is None and candidate < today:
        candidate = date(candidate.year + 1, candidate.month, candidate.day)
    return candidate


def _extract_dates(text: str, today: date) -> list[date]:
    dates: list[date] = []
    for match in DATE_RE.finditer(text.casefold()):
        month_text = match.group("month") or match.group("month2")
        day_text = match.group("day") or match.group("day2")
        year_text = match.group("year") or match.group("year2")
        month = RU_MONTHS.get(month_text) or EN_MONTHS.get(month_text)
        if not month or not day_text:
            continue
        parsed = _future_date(int(day_text), month, int(year_text) if year_text else None, today)
        if parsed:
            dates.append(parsed)
    return dates


def _clean_place(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\b(на|on|from|с|по|туда|обратно|for|для)\b.*$", "", value.strip(), flags=re.I).strip(" ,.-")
    return cleaned or None


def _extract_route(text: str) -> tuple[str | None, str | None]:
    patterns = [
        r"из\s+(?P<origin>.+?)\s+в\s+(?P<destination>.+?)(?=\s+(?:с|на|туда|обратно|для|\d{1,2}\s)|$)",
        r"from\s+(?P<origin>.+?)\s+to\s+(?P<destination>.+?)(?=\s+(?:on|from|for|\d{1,2}\s|january|february|march|april|may|june|july|august|september|october|november|december)|$)",
        r"(?P<origin>[A-Za-zА-Яа-яЁё -]+?)\s*(?:→|-)\s*(?P<destination>[A-Za-zА-Яа-яЁё -]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return _clean_place(match.group("origin")), _clean_place(match.group("destination"))

    without_prefix = re.sub(r"^(найди( мне)? билеты|ищу рейс|билет|search flights|find flights|tickets)\s+", "", text.strip(), flags=re.I)
    dest_only = re.search(r"^(?:в|to)\s+(?P<destination>.+?)(?=\s+(?:на|on|с|from|для|for|\d{1,2}\s)|$)", without_prefix, re.I)
    if dest_only:
        return None, _clean_place(dest_only.group("destination"))
    before_date = DATE_RE.split(without_prefix, maxsplit=1)[0]
    words = [part for part in before_date.split() if part.casefold() not in {"из", "в", "from", "to"}]
    if len(words) >= 2:
        return words[0], words[1]
    return None, None


def _extract_passengers(text: str) -> PassengerCounts:
    adults = None
    children = 0
    infants = 0
    adult_match = re.search(r"(\d+)\s*(?:взросл\w*|adult[s]?)", text, re.I)
    child_match = re.search(r"(\d+)\s*(?:реб[её]н\w*|дет\w*|child|children)", text, re.I)
    infant_match = re.search(r"(\d+)\s*(?:младен\w*|infant[s]?)", text, re.I)
    if adult_match:
        adults = int(adult_match.group(1))
    if child_match:
        children = int(child_match.group(1))
    if infant_match:
        infants = int(infant_match.group(1))
    return PassengerCounts(adults=max(1, adults or 1), children=max(0, children), infants=max(0, infants))


def parse_natural_search(text: str, *, language_code: str = "ru", today: date | None = None) -> NaturalSearchParseResult:
    """Extract route, dates, trip type, and passengers from a RU/EN free-form query."""
    current = today or date.today()
    origin, destination = _extract_route(text)
    dates = _extract_dates(text, current)
    passengers = _extract_passengers(text)
    result = NaturalSearchParseResult(origin_text=origin, destination_text=destination, passengers=passengers)
    if dates:
        result.departure_date = dates[0].isoformat()
    if len(dates) > 1:
        result.return_date = dates[1].isoformat()
        result.trip_type = "round_trip"
    elif re.search(r"\b(round trip|return|обратно|туда и обратно|по)\b", text, re.I):
        result.trip_type = "round_trip"

    for field_name, value in (("origin", origin), ("destination", destination), ("departure_date", result.departure_date)):
        if not value:
            result.missing.append(field_name)
    recognized = 4 - len(result.missing) + (1 if result.return_date else 0)
    result.confidence = min(1.0, recognized / 5)
    return result
