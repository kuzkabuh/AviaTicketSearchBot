from __future__ import annotations

import asyncio
import sqlite3

import db
from app.news.airline_registry import seed_initial_airlines_and_sources
from app.news.airline_sync_service import AirlineSyncService
from app.news.classifier import classify_news, extract_promo_code
from app.news.deduplicator import build_content_hash
from app.news.models import FetchedNewsItem
from app.news.parser import enrich_item
from app.news.repository import AirlineRepository, NewsRepository, NewsSourceRepository, NewsSubscriptionRepository, ensure_news_schema
from app.news.route_extractor import extract_route_names


def memory_db() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    ensure_news_schema(connection)
    return connection


def test_news_tables_and_migration_idempotent() -> None:
    connection = memory_db()
    ensure_news_schema(connection)
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"airlines", "airline_news_sources", "airline_news", "user_news_subscriptions", "user_news_deliveries"} <= tables


def test_seed_registry_counts() -> None:
    connection = memory_db()
    stats = seed_initial_airlines_and_sources(connection)
    airline_stats = AirlineRepository(connection).stats()
    assert stats["seed_airlines_total"] >= 20
    assert airline_stats["russian"] >= 18
    assert airline_stats["with_sources"] >= 18


def test_airline_sync_from_test_reference(tmp_path) -> None:
    original = db.settings.database_path
    object.__setattr__(db.settings, "database_path", str(tmp_path / "news.sqlite3"))
    try:
        result = asyncio.run(AirlineSyncService().sync(items=[
            {"code": "SU", "icao_code": "AFL", "name": "Aeroflot", "country": "Russia", "is_active": True},
            {"code": "QR", "icao_code": "QTR", "name": "Qatar Airways", "country": "Qatar", "is_active": True},
        ], seed_if_empty=False))
        assert result == {"loaded": 2, "created": 2, "updated": 0, "russian": 1}
        with sqlite3.connect(db.settings.database_path) as connection:
            connection.row_factory = sqlite3.Row
            su = dict(connection.execute("SELECT * FROM airlines WHERE airline_code = 'SU'").fetchone())
            assert su["is_russian"] == 1
            assert su["source_origin"] == "aviasales_reference"
    finally:
        object.__setattr__(db.settings, "database_path", original)


def test_airline_sync_preserves_manual_source_fields() -> None:
    connection = memory_db()
    repo = AirlineRepository(connection)
    row, _ = repo.upsert_airline({"airline_code": "SU", "official_name": "Manual Aeroflot", "country_code": "RU", "is_russian": True, "official_website": "https://manual.example", "has_news_source": 1, "news_source_status": "configured"})
    connection.commit()
    # Use repository normalization logic directly on the same connection to keep test deterministic.
    updated, created = repo.upsert_airline({"airline_code": "SU", "official_name": "Aeroflot", "country_code": "RU", "is_russian": True, "source_origin": "aviasales_reference"}, preserve_manual_sources=True)
    assert not created
    assert updated["official_website"] == "https://manual.example"
    assert updated["news_source_status"] == "configured"


def test_record_ticket_airlines_updates_counts() -> None:
    connection = memory_db()
    repo = AirlineRepository(connection)
    assert repo.record_ticket_airlines(["SU", "SU", "S7"]) == 3
    su = repo.get_by_iata("SU")
    assert su is not None
    assert su["ticket_results_count"] == 2
    assert su["first_seen_in_ticket_results_at"]
    assert su["last_seen_in_ticket_results_at"]


def test_news_deduplication_by_external_url_hash() -> None:
    connection = memory_db()
    airline, _ = AirlineRepository(connection).upsert_airline({"airline_code": "S7", "official_name": "S7 Airlines"})
    source, _ = NewsSourceRepository(connection).upsert_source({"airline_id": airline["id"], "airline_code": "S7", "airline_name": "S7 Airlines", "source_name": "S7", "source_type": "rss", "source_url": "https://s7.example/rss", "source_role": "news", "language_code": "ru"})
    repo = NewsRepository(connection)
    content_hash = build_content_hash("Распродажа", "https://s7.example/news/1", "2026-05-12", "S7")
    payload = {"source_id": source["id"], "airline_id": airline["id"], "airline_code": "S7", "airline_name": "S7", "category": "discount_sale", "title_original": "Распродажа", "source_url": "https://s7.example/news/1", "content_hash": content_hash, "external_id": "guid-1"}
    _, created = repo.create_news(payload)
    assert created
    _, created = repo.create_news(payload)
    assert not created
    payload2 = {**payload, "external_id": "guid-2"}
    _, created = repo.create_news(payload2)
    assert not created


def test_classifier_categories_and_promo_extraction() -> None:
    assert classify_news("Большая распродажа билетов").category == "discount_sale"
    assert classify_news("Ваш промокод SUMMER20 на скидку").category == "promo_code"
    assert classify_news("Авиакомпания запускает полёты из Москвы в Казань").category == "new_route"
    assert classify_news("Qatar Airways resumes flights between Doha and Helsinki").category == "route_resumed"
    assert classify_news("Открыто летнее расписание").category == "seasonal_schedule"
    assert extract_promo_code("Промокод: AVIA2026 действует до 31.05") == "AVIA2026"


def test_route_extractor_ru_and_en() -> None:
    ru = extract_route_names("S7 открывает рейсы из Красноярска в Горно-Алтайск.")
    en = extract_route_names("Qatar Airways resumes flights between Doha and Helsinki.")
    assert ru.origin_name == "Красноярска"
    assert ru.destination_name == "Горно-Алтайск"
    assert en.origin_name == "Doha"
    assert en.destination_name == "Helsinki"


def test_user_news_subscriptions_and_delivery() -> None:
    connection = memory_db()
    repo = NewsSubscriptionRepository(connection)
    first = repo.upsert_subscription(42, "all_russian_airlines", notification_mode="instant")
    second = repo.upsert_subscription(42, "all_russian_airlines", notification_mode="digest_daily")
    assert first["id"] == second["id"]
    assert second["notification_mode"] == "digest_daily"
    assert repo.record_delivery(42, 7, "instant")
    assert not repo.record_delivery(42, 7, "instant")


def test_enrich_item_fills_news_fields() -> None:
    item = FetchedNewsItem(title="Промокод AVIA2026 на билеты", link="https://example.com/1", summary="Акция до 31.05.2026")
    data = enrich_item(item, {"airline_name": "S7", "language_code": "ru"})
    assert data["category"] == "promo_code"
    assert data["promo_code"] == "AVIA2026"
    assert data["title_ru"] == item.title
    assert data["content_hash"]


def test_rss_feed_parser() -> None:
    from app.news.fetchers.rss_fetcher import parse_feed
    xml = """<rss><channel><item><title>S7 sale</title><link>https://s7.example/news/1</link><description>Discount</description><guid>g1</guid><pubDate>Tue, 12 May 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
    items = parse_feed(xml, {"language_code": "en"})
    assert len(items) == 1
    assert items[0].title == "S7 sale"
    assert items[0].external_id == "g1"


def test_html_parser_missing_fields_resilient() -> None:
    from app.news.fetchers.html_fetcher import parse_html_items
    html = '<html><body><a href="/about/news/1">Smartavia opens new route 12.05.2026</a><a href="/contacts">Contacts</a></body></html>'
    items = parse_html_items(html, {"source_url": "https://flysmartavia.com/about/news/", "language_code": "en"})
    assert len(items) == 1
    assert items[0].published_at == "12.05.2026"
