"""Replaceable RU/EN short text preparation service for news cards."""

from __future__ import annotations

CYRILLIC_MARKERS = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюя")


def detect_language(text: str | None, fallback: str = "ru") -> str:
    sample = (text or "").lower()
    return "ru" if any(char in CYRILLIC_MARKERS for char in sample) else ("en" if sample else fallback)


def prepare_bilingual_text(title: str, summary: str | None, original_language: str | None = None) -> dict[str, str | None]:
    """Prepare card-sized localized fields.

    This fallback intentionally does not fake machine translation. It fills the
    original language and leaves the other language empty for a future provider.
    Formatters fall back safely to original fields when a translation is absent.
    """
    language = original_language or detect_language(" ".join([title, summary or ""]))
    short_summary = (summary or "").strip()
    if len(short_summary) > 500:
        short_summary = short_summary[:497].rstrip() + "..."
    if language == "en":
        return {"title_en": title, "summary_en": short_summary or None, "title_ru": None, "summary_ru": None}
    return {"title_ru": title, "summary_ru": short_summary or None, "title_en": None, "summary_en": None}
