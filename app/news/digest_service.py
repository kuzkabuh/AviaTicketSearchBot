"""Automatic airline news collections and user digests."""

from __future__ import annotations

from app.news.formatters import format_digest
from app.news.personalization_service import score_news_for_user
from app.news.repository import connect, ensure_news_schema
from services.i18n import translate


def top_deals_of_day(language: str = "ru") -> str:
    with connect() as connection:
        ensure_news_schema(connection)
        rows = connection.execute(
            """
            SELECT n.* FROM airline_news n JOIN airlines a ON a.id = n.airline_id
            WHERE n.status IN ('approved','published') AND n.category IN ('discount_sale','promo_code')
              AND datetime(COALESCE(n.published_at, n.detected_at)) >= datetime('now', '-1 day')
            ORDER BY a.is_russian DESC, COALESCE(n.published_at, n.detected_at) DESC LIMIT 10
            """
        ).fetchall()
        return format_digest(translate(language, "news.digests.top_deals_day"), [dict(row) for row in rows], language)


def new_routes_of_week(language: str = "ru") -> str:
    with connect() as connection:
        ensure_news_schema(connection)
        rows = connection.execute(
            """
            SELECT * FROM airline_news
            WHERE status IN ('approved','published') AND category IN ('new_route','route_resumed','seasonal_schedule')
              AND datetime(COALESCE(published_at, detected_at)) >= datetime('now', '-7 days')
            ORDER BY COALESCE(published_at, detected_at) DESC LIMIT 10
            """
        ).fetchall()
        return format_digest(translate(language, "news.digests.new_routes_week"), [dict(row) for row in rows], language)


def personalized_collection(user_id: int, language: str = "ru") -> str:
    with connect() as connection:
        ensure_news_schema(connection)
        rows = [dict(row) for row in connection.execute("SELECT * FROM airline_news WHERE status IN ('approved','published') ORDER BY COALESCE(published_at, detected_at) DESC LIMIT 100")]
        ranked = sorted(((score_news_for_user(connection, user_id, row), row) for row in rows), key=lambda item: item[0], reverse=True)
        selected = [row for score, row in ranked if score > 0][:10]
        return format_digest(translate(language, "news.digests.for_you"), selected, language)
