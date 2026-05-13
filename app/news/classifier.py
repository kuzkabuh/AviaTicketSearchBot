"""Rule-based airline news classifier and promotion metadata extractor."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.news.models import ClassificationResult

KEYWORDS: dict[str, tuple[str, ...]] = {
    "discount_sale": (
        "скидка", "скидки", "распродажа", "акция", "специальные цены", "спецпредлож", "sale", "discount", "fares from", "special fares",
    ),
    "promo_code": ("промокод", "промо-код", "купон", "код на скидку", "coupon", "promo code", "promocode"),
    "new_route": (
        "новый маршрут", "новое направление", "открывает рейсы", "открывает продажу билетов", "запускает полёты", "запускает полеты", "launches new route", "starts flights", "new service", "new route",
    ),
    "route_resumed": ("возобновляет рейсы", "возобновление рейсов", "возвращает полёты", "возвращает полеты", "resumes flights", "restores service"),
    "frequency_increase": ("увеличивает частоту", "дополнительные рейсы", "больше рейсов", "more flights", "increases frequency", "additional flights"),
    "seasonal_schedule": ("летнее расписание", "зимнее расписание", "сезонное расписание", "seasonal schedule", "summer schedule", "winter schedule"),
}
PROMO_RE = re.compile(r"(?i)(?:промокод|promo\s*code|coupon|код)[:\s]+([A-ZА-Я0-9][A-ZА-Я0-9_-]{3,20})")
DATE_RE = re.compile(r"(?P<day>\d{1,2})[./-](?P<month>\d{1,2})(?:[./-](?P<year>\d{2,4}))?")


def classify_news(title: str | None, summary: str | None = None, content: str | None = None) -> ClassificationResult:
    """Classify a news item by localized keywords."""
    text = " ".join(part for part in (title, summary, content) if part).lower()
    best_category = "general_news"
    best_matches: list[str] = []
    for category, keywords in KEYWORDS.items():
        matches = [keyword for keyword in keywords if keyword in text]
        if len(matches) > len(best_matches):
            best_category = category
            best_matches = matches
    promo_matches = [keyword for keyword in KEYWORDS["promo_code"] if keyword in text]
    if promo_matches:
        best_category = "promo_code"
        best_matches = promo_matches
    confidence = min(0.95, 0.35 + 0.2 * len(best_matches)) if best_matches else 0.2
    if confidence < 0.4:
        best_category = "general_news"
    return ClassificationResult(best_category, confidence, best_matches)


def extract_promo_code(text: str | None) -> str | None:
    match = PROMO_RE.search(text or "")
    return match.group(1).upper() if match else None


def _normalize_date(day: str, month: str, year: str | None) -> str | None:
    current_year = datetime.now(timezone.utc).year
    year_int = int(year) if year else current_year
    if year_int < 100:
        year_int += 2000
    try:
        return datetime(year_int, int(month), int(day)).date().isoformat()
    except ValueError:
        return None


def extract_sale_dates(text: str | None) -> dict[str, str | None]:
    """Extract first simple DD.MM[.YYYY] date as sale end; range support can be added later."""
    matches = list(DATE_RE.finditer(text or ""))
    sale_end = _normalize_date(**matches[0].groupdict()) if matches else None
    travel_start = _normalize_date(**matches[1].groupdict()) if len(matches) > 1 else None
    travel_end = _normalize_date(**matches[2].groupdict()) if len(matches) > 2 else None
    return {"sale_end_at": sale_end, "travel_start_at": travel_start, "travel_end_at": travel_end}
