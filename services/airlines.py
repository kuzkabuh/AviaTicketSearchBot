"""Airline code normalization helpers.

A small built-in map covers Russian carriers and common international airlines.
The news module can enrich the same airlines from Aviasales/Travelpayouts data;
formatters use this fallback so user-facing cards never show only opaque codes
when a known name is available.
"""

from __future__ import annotations

AIRLINE_NAMES: dict[str, str] = {
    "SU": "Аэрофлот",
    "DP": "Победа",
    "FV": "Россия",
    "S7": "S7 Airlines",
    "U6": "Уральские авиалинии",
    "N4": "Nordwind Airlines",
    "5N": "Smartavia",
    "WZ": "Red Wings",
    "UT": "Utair",
    "A4": "Азимут",
    "R3": "Якутия",
    "YC": "Ямал",
    "6R": "Алроса",
    "EO": "Икар / Pegas Fly",
    "IO": "ИрАэро",
    "HZ": "Аврора",
    "D2": "Северсталь Авиа",
    "7R": "РусЛайн",
    "Y7": "NordStar",
    "RT": "ЮВТ Аэро",
    "QR": "Qatar Airways",
    "EK": "Emirates",
}


def normalize_airline_code(code: object) -> str:
    return str(code or "").strip().upper()


def format_airline_name(code_or_name: object) -> str:
    value = str(code_or_name or "").strip()
    code = normalize_airline_code(value)
    if not value or code in {"НЕ УКАЗАНА", "-"}:
        return "не указана"
    name = AIRLINE_NAMES.get(code)
    return f"{name} ({code})" if name else value
