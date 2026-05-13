"""Localized card and digest formatters for airline news."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from services.i18n import translate

CATEGORY_ICONS = {
    "discount_sale": "🔥", "promo_code": "🎟", "new_route": "🛫", "route_resumed": "🔄", "frequency_increase": "✈️", "seasonal_schedule": "📅", "general_news": "📰",
}


def _date(value: str | None, language: str) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value[:10]
    return dt.strftime("%d.%m.%Y") if language == "ru" else dt.strftime("%b %d, %Y")


def news_title(news: dict[str, Any], language: str) -> str:
    return str(news.get(f"title_{language}") or news.get("title_original") or "")


def news_summary(news: dict[str, Any], language: str) -> str:
    return str(news.get(f"summary_{language}") or news.get("summary_original") or "")


def format_news_card(news: dict[str, Any], language: str = "ru") -> str:
    category = str(news.get("category") or "general_news")
    icon = CATEGORY_ICONS.get(category, "📰")
    title = news_title(news, language)
    summary = news_summary(news, language)
    lines = [f"{icon} <b>{escape(str(news.get('airline_name') or ''))} — {escape(title)}</b>"]
    if summary:
        lines.extend(["", escape(summary)])
    lines.extend([
        "",
        f"{escape(translate(language, 'news.cards.category'))}: {escape(translate(language, f'news.categories.{category}'))}",
        f"{escape(translate(language, 'news.cards.airline'))}: {escape(str(news.get('airline_name') or '—'))}",
        f"{escape(translate(language, 'news.cards.published'))}: {_date(news.get('published_at') or news.get('detected_at'), language)}",
    ])
    if news.get("promo_code"):
        lines.append(f"{escape(translate(language, 'news.cards.promo_code'))}: <code>{escape(str(news['promo_code']))}</code>")
    return "\n".join(lines)


def format_digest(title: str, news_items: list[dict[str, Any]], language: str = "ru", limit: int = 5) -> str:
    lines = [title, ""]
    if not news_items:
        lines.append(translate(language, "news.digests.empty"))
        return "\n".join(lines)
    for idx, news in enumerate(news_items[:limit], start=1):
        lines.append(f"{idx}. {news.get('airline_name')}: {news_title(news, language)}")
    return "\n".join(lines)


def format_admin_news_card(news: dict[str, Any]) -> str:
    route = "—"
    if news.get("related_origin_name") or news.get("related_destination_name"):
        route = f"{news.get('related_origin_name') or '?'} → {news.get('related_destination_name') or '?'}"
    return (
        f"📰 <b>Новость #{news.get('id')}</b>\n"
        f"Авиакомпания: <b>{escape(str(news.get('airline_name') or '—'))}</b> ({escape(str(news.get('airline_code') or '—'))})\n"
        f"Категория: <code>{escape(str(news.get('category') or '—'))}</code>\n"
        f"Статус: <code>{escape(str(news.get('status') or '—'))}</code>\n"
        f"Опубликовано источником: {escape(str(news.get('published_at') or '—'))}\n"
        f"Маршрут: {escape(route)}\n"
        f"Промокод: {escape(str(news.get('promo_code') or '—'))}\n\n"
        f"<b>{escape(str(news.get('title_original') or ''))}</b>\n"
        f"{escape(str(news.get('summary_original') or '')[:700])}\n\n"
        f"Источник: {escape(str(news.get('source_url') or '—'))}"
    )
