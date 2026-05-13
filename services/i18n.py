"""JSON-backed localization service with database-aware user language lookup."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import db

SUPPORTED_LANGUAGES = {"ru", "en"}
DEFAULT_LANGUAGE = "ru"
DEFAULT_CURRENCY_BY_LANGUAGE = {"ru": "RUB", "en": "USD"}
DEFAULT_MARKET_BY_LANGUAGE = {"ru": "ru", "en": "us"}
SUPPORTED_CURRENCIES = {"RUB", "USD", "EUR"}
_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


@lru_cache(maxsize=8)
def load_locale(language_code: str) -> dict[str, str]:
    """Load one locale JSON file and cache it for process lifetime."""
    normalized = language_code if language_code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    with (_LOCALES_DIR / f"{normalized}.json").open(encoding="utf-8") as file:
        return json.load(file)


def normalize_language(language_code: str | None) -> str:
    return language_code if language_code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def normalize_currency(currency_code: str | None) -> str:
    value = (currency_code or "").upper()
    return value if value in SUPPORTED_CURRENCIES else "RUB"


def defaults_for_language(language_code: str | None) -> tuple[str, str]:
    language = normalize_language(language_code)
    return DEFAULT_CURRENCY_BY_LANGUAGE[language], DEFAULT_MARKET_BY_LANGUAGE[language]


def translate(language_code: str | None, key: str, **kwargs: Any) -> str:
    """Translate by explicit language code with RU fallback and str.format kwargs."""
    language = normalize_language(language_code)
    value = load_locale(language).get(key) or load_locale(DEFAULT_LANGUAGE).get(key) or key
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            return value
    return value


async def user_language(user_id: int | None) -> str:
    """Return user's saved language from DB or fallback to RU."""
    if user_id is None:
        return DEFAULT_LANGUAGE
    profile = await db.get_user_profile(user_id)
    return normalize_language((profile or {}).get("language_code"))


async def t(user_id: int | None, key: str, **kwargs: Any) -> str:
    """Translate key for a Telegram user, falling back to Russian when needed."""
    return translate(await user_language(user_id), key, **kwargs)
