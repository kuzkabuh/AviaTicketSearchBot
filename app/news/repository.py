"""SQLite repositories and idempotent schema migration for airline news."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from typing import Any, Iterable

from config import settings
from db import utcnow_iso

logger = logging.getLogger(__name__)

NEWS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS airlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    airline_code TEXT NULL,
    icao_code TEXT NULL,
    official_name TEXT NOT NULL,
    display_name_ru TEXT NULL,
    display_name_en TEXT NULL,
    country_code TEXT NULL,
    country_name TEXT NULL,
    is_russian INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NULL,
    source_origin TEXT NOT NULL DEFAULT 'manual',
    official_website TEXT NULL,
    has_news_source INTEGER NOT NULL DEFAULT 0,
    news_source_status TEXT NOT NULL DEFAULT 'unknown',
    first_seen_in_ticket_results_at TEXT NULL,
    last_seen_in_ticket_results_at TEXT NULL,
    ticket_results_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_airlines_code ON airlines(airline_code) WHERE airline_code IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_airlines_name_country ON airlines(official_name, country_code);
CREATE INDEX IF NOT EXISTS idx_airlines_russian ON airlines(is_russian);
CREATE INDEX IF NOT EXISTS idx_airlines_source_status ON airlines(news_source_status);

CREATE TABLE IF NOT EXISTS airline_news_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    airline_id INTEGER NOT NULL,
    airline_code TEXT NULL,
    airline_name TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_role TEXT NOT NULL DEFAULT 'news',
    language_code TEXT NOT NULL,
    country_code TEXT NULL,
    parser_key TEXT NULL,
    selectors_json TEXT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    check_interval_minutes INTEGER NOT NULL DEFAULT 360,
    last_checked_at TEXT NULL,
    last_success_at TEXT NULL,
    last_error_at TEXT NULL,
    last_error_message TEXT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (airline_id) REFERENCES airlines(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_airline_news_sources_url ON airline_news_sources(airline_id, source_url, source_role, language_code);
CREATE INDEX IF NOT EXISTS idx_airline_news_sources_active ON airline_news_sources(is_active, last_checked_at);

CREATE TABLE IF NOT EXISTS airline_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    airline_id INTEGER NOT NULL,
    airline_code TEXT NULL,
    airline_name TEXT NOT NULL,
    category TEXT NULL,
    title_original TEXT NOT NULL,
    summary_original TEXT NULL,
    content_original TEXT NULL,
    title_ru TEXT NULL,
    summary_ru TEXT NULL,
    title_en TEXT NULL,
    summary_en TEXT NULL,
    source_url TEXT NOT NULL,
    image_url TEXT NULL,
    published_at TEXT NULL,
    detected_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    moderation_comment TEXT NULL,
    content_hash TEXT NOT NULL,
    external_id TEXT NULL,
    related_origin_iata TEXT NULL,
    related_destination_iata TEXT NULL,
    related_origin_name TEXT NULL,
    related_destination_name TEXT NULL,
    promo_code TEXT NULL,
    sale_end_at TEXT NULL,
    travel_start_at TEXT NULL,
    travel_end_at TEXT NULL,
    published_to_users_at TEXT NULL,
    FOREIGN KEY (source_id) REFERENCES airline_news_sources(id),
    FOREIGN KEY (airline_id) REFERENCES airlines(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_airline_news_hash ON airline_news(content_hash);
CREATE UNIQUE INDEX IF NOT EXISTS ux_airline_news_external ON airline_news(source_id, external_id) WHERE external_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_airline_news_source_url ON airline_news(source_url);
CREATE INDEX IF NOT EXISTS idx_airline_news_status ON airline_news(status, published_at);
CREATE INDEX IF NOT EXISTS idx_airline_news_category ON airline_news(category);
CREATE INDEX IF NOT EXISTS idx_airline_news_airline ON airline_news(airline_id);

CREATE TABLE IF NOT EXISTS user_news_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subscription_type TEXT NOT NULL,
    category TEXT NULL,
    airline_id INTEGER NULL,
    airline_code TEXT NULL,
    notification_mode TEXT NOT NULL DEFAULT 'digest_daily',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (airline_id) REFERENCES airlines(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_user_news_subscription ON user_news_subscriptions(user_id, subscription_type, COALESCE(category, ''), COALESCE(airline_id, 0), COALESCE(airline_code, ''));
CREATE INDEX IF NOT EXISTS idx_user_news_subscriptions_user ON user_news_subscriptions(user_id, is_active);

CREATE TABLE IF NOT EXISTS user_news_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    news_id INTEGER NOT NULL,
    delivery_type TEXT NOT NULL,
    delivered_at TEXT NOT NULL,
    FOREIGN KEY (news_id) REFERENCES airline_news(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_user_news_delivery ON user_news_deliveries(user_id, news_id, delivery_type);
"""

TABLE_COLUMNS: dict[str, dict[str, str]] = {
    "airlines": {
        "airline_code": "TEXT NULL", "icao_code": "TEXT NULL", "official_name": "TEXT NOT NULL DEFAULT ''", "display_name_ru": "TEXT NULL", "display_name_en": "TEXT NULL", "country_code": "TEXT NULL", "country_name": "TEXT NULL", "is_russian": "INTEGER NOT NULL DEFAULT 0", "is_active": "INTEGER NULL", "source_origin": "TEXT NOT NULL DEFAULT 'manual'", "official_website": "TEXT NULL", "has_news_source": "INTEGER NOT NULL DEFAULT 0", "news_source_status": "TEXT NOT NULL DEFAULT 'unknown'", "first_seen_in_ticket_results_at": "TEXT NULL", "last_seen_in_ticket_results_at": "TEXT NULL", "ticket_results_count": "INTEGER NOT NULL DEFAULT 0", "created_at": "TEXT NOT NULL DEFAULT ''", "updated_at": "TEXT NOT NULL DEFAULT ''",
    },
    "airline_news_sources": {
        "airline_id": "INTEGER NOT NULL DEFAULT 0", "airline_code": "TEXT NULL", "airline_name": "TEXT NOT NULL DEFAULT ''", "source_name": "TEXT NOT NULL DEFAULT ''", "source_type": "TEXT NOT NULL DEFAULT 'html'", "source_url": "TEXT NOT NULL DEFAULT ''", "source_role": "TEXT NOT NULL DEFAULT 'news'", "language_code": "TEXT NOT NULL DEFAULT 'ru'", "country_code": "TEXT NULL", "parser_key": "TEXT NULL", "selectors_json": "TEXT NULL", "is_active": "INTEGER NOT NULL DEFAULT 1", "check_interval_minutes": "INTEGER NOT NULL DEFAULT 360", "last_checked_at": "TEXT NULL", "last_success_at": "TEXT NULL", "last_error_at": "TEXT NULL", "last_error_message": "TEXT NULL", "created_at": "TEXT NOT NULL DEFAULT ''", "updated_at": "TEXT NOT NULL DEFAULT ''",
    },
    "airline_news": {
        "source_id": "INTEGER NOT NULL DEFAULT 0", "airline_id": "INTEGER NOT NULL DEFAULT 0", "airline_code": "TEXT NULL", "airline_name": "TEXT NOT NULL DEFAULT ''", "category": "TEXT NULL", "title_original": "TEXT NOT NULL DEFAULT ''", "summary_original": "TEXT NULL", "content_original": "TEXT NULL", "title_ru": "TEXT NULL", "summary_ru": "TEXT NULL", "title_en": "TEXT NULL", "summary_en": "TEXT NULL", "source_url": "TEXT NOT NULL DEFAULT ''", "image_url": "TEXT NULL", "published_at": "TEXT NULL", "detected_at": "TEXT NOT NULL DEFAULT ''", "updated_at": "TEXT NOT NULL DEFAULT ''", "status": "TEXT NOT NULL DEFAULT 'pending'", "moderation_comment": "TEXT NULL", "content_hash": "TEXT NOT NULL DEFAULT ''", "external_id": "TEXT NULL", "related_origin_iata": "TEXT NULL", "related_destination_iata": "TEXT NULL", "related_origin_name": "TEXT NULL", "related_destination_name": "TEXT NULL", "promo_code": "TEXT NULL", "sale_end_at": "TEXT NULL", "travel_start_at": "TEXT NULL", "travel_end_at": "TEXT NULL", "published_to_users_at": "TEXT NULL",
    },
    "user_news_subscriptions": {
        "user_id": "INTEGER NOT NULL DEFAULT 0", "subscription_type": "TEXT NOT NULL DEFAULT 'all'", "category": "TEXT NULL", "airline_id": "INTEGER NULL", "airline_code": "TEXT NULL", "notification_mode": "TEXT NOT NULL DEFAULT 'digest_daily'", "is_active": "INTEGER NOT NULL DEFAULT 1", "created_at": "TEXT NOT NULL DEFAULT ''", "updated_at": "TEXT NOT NULL DEFAULT ''",
    },
    "user_news_deliveries": {"user_id": "INTEGER NOT NULL DEFAULT 0", "news_id": "INTEGER NOT NULL DEFAULT 0", "delivery_type": "TEXT NOT NULL DEFAULT 'instant'", "delivered_at": "TEXT NOT NULL DEFAULT ''"},
}


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_news_schema(connection: sqlite3.Connection) -> None:
    """Create/repair news schema. Safe to call on every bot start."""
    connection.executescript(NEWS_SCHEMA_SQL)
    for table, columns in TABLE_COLUMNS.items():
        existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        for column, definition in columns.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                logger.info("Added missing news column %s.%s", table, column)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _clean_code(code: str | None) -> str | None:
    value = (code or "").strip().upper()
    return value or None


class AirlineRepository:
    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self.connection = connection or connect()

    def get_by_iata(self, airline_code: str | None) -> dict[str, Any] | None:
        code = _clean_code(airline_code)
        if not code:
            return None
        return row_to_dict(self.connection.execute("SELECT * FROM airlines WHERE airline_code = ?", (code,)).fetchone())

    def get_russian_airlines(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM airlines WHERE is_russian = 1 ORDER BY official_name")]

    def get_without_news_source(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM airlines WHERE has_news_source = 0 OR news_source_status != 'configured' ORDER BY is_russian DESC, official_name")]

    def upsert_airline(self, data: dict[str, Any], preserve_manual_sources: bool = True) -> tuple[dict[str, Any], bool]:
        now = utcnow_iso()
        code = _clean_code(data.get("airline_code"))
        existing = self.get_by_iata(code) if code else None
        if not existing:
            existing = row_to_dict(self.connection.execute("SELECT * FROM airlines WHERE official_name = ? AND COALESCE(country_code, '') = COALESCE(?, '')", (data.get("official_name"), data.get("country_code"))).fetchone())
        fields = {
            "airline_code": code,
            "icao_code": _clean_code(data.get("icao_code")),
            "official_name": data.get("official_name") or data.get("display_name_en") or code or "Unknown airline",
            "display_name_ru": data.get("display_name_ru"),
            "display_name_en": data.get("display_name_en"),
            "country_code": _clean_code(data.get("country_code")),
            "country_name": data.get("country_name"),
            "is_russian": int(bool(data.get("is_russian"))),
            "is_active": data.get("is_active"),
            "source_origin": data.get("source_origin") or "manual",
            "official_website": data.get("official_website"),
            "has_news_source": int(bool(data.get("has_news_source", 0))),
            "news_source_status": data.get("news_source_status") or "unknown",
            "updated_at": now,
        }
        if existing:
            if preserve_manual_sources:
                for key in ("official_website", "has_news_source", "news_source_status"):
                    if existing.get(key) not in (None, "", 0, "unknown"):
                        fields[key] = existing[key]
            assignments = ", ".join(f"{key} = ?" for key in fields)
            self.connection.execute(f"UPDATE airlines SET {assignments} WHERE id = ?", (*fields.values(), existing["id"]))
            return row_to_dict(self.connection.execute("SELECT * FROM airlines WHERE id = ?", (existing["id"],)).fetchone()) or {}, False
        fields["created_at"] = now
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        cursor = self.connection.execute(f"INSERT INTO airlines ({columns}) VALUES ({placeholders})", tuple(fields.values()))
        return row_to_dict(self.connection.execute("SELECT * FROM airlines WHERE id = ?", (cursor.lastrowid,)).fetchone()) or {}, True

    def record_ticket_airlines(self, airline_codes: Iterable[str | None]) -> int:
        now = utcnow_iso()
        changed = 0
        for raw_code in airline_codes:
            code = _clean_code(raw_code)
            if not code or code in {"НЕ УКАЗАНА", "UNKNOWN"}:
                continue
            row = self.get_by_iata(code)
            if row:
                first_seen = row.get("first_seen_in_ticket_results_at") or now
                self.connection.execute(
                    "UPDATE airlines SET first_seen_in_ticket_results_at = ?, last_seen_in_ticket_results_at = ?, ticket_results_count = COALESCE(ticket_results_count, 0) + 1, updated_at = ? WHERE id = ?",
                    (first_seen, now, now, row["id"]),
                )
            else:
                self.upsert_airline({"airline_code": code, "official_name": code, "source_origin": "aviasales_search_results", "news_source_status": "unknown"})
                self.connection.execute("UPDATE airlines SET first_seen_in_ticket_results_at = ?, last_seen_in_ticket_results_at = ?, ticket_results_count = 1 WHERE airline_code = ?", (now, now, code))
            changed += 1
        return changed

    def update_news_source_status(self, airline_id: int, status: str, has_source: bool | None = None) -> None:
        now = utcnow_iso()
        if has_source is None:
            self.connection.execute("UPDATE airlines SET news_source_status = ?, updated_at = ? WHERE id = ?", (status, now, airline_id))
        else:
            self.connection.execute("UPDATE airlines SET news_source_status = ?, has_news_source = ?, updated_at = ? WHERE id = ?", (status, int(has_source), now, airline_id))

    def stats(self) -> dict[str, int]:
        row = self.connection.execute(
            """
            SELECT COUNT(*) total,
                   SUM(CASE WHEN is_russian = 1 THEN 1 ELSE 0 END) russian,
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) active,
                   SUM(CASE WHEN has_news_source = 1 THEN 1 ELSE 0 END) with_sources,
                   SUM(CASE WHEN has_news_source = 0 THEN 1 ELSE 0 END) without_sources,
                   SUM(CASE WHEN ticket_results_count > 0 THEN 1 ELSE 0 END) seen_in_tickets
            FROM airlines
            """
        ).fetchone()
        return {key: int(row[key] or 0) for key in row.keys()} if row else {}


class NewsSourceRepository:
    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self.connection = connection or connect()

    def upsert_source(self, data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        now = utcnow_iso()
        existing = row_to_dict(self.connection.execute(
            "SELECT * FROM airline_news_sources WHERE airline_id = ? AND source_url = ? AND source_role = ? AND language_code = ?",
            (data["airline_id"], data["source_url"], data.get("source_role", "news"), data.get("language_code", "ru")),
        ).fetchone())
        fields = {**data, "selectors_json": json.dumps(data.get("selectors"), ensure_ascii=False) if data.get("selectors") else data.get("selectors_json"), "updated_at": now}
        fields.pop("selectors", None)
        if existing:
            assignments = ", ".join(f"{key} = ?" for key in fields)
            self.connection.execute(f"UPDATE airline_news_sources SET {assignments} WHERE id = ?", (*fields.values(), existing["id"]))
            return row_to_dict(self.connection.execute("SELECT * FROM airline_news_sources WHERE id = ?", (existing["id"],)).fetchone()) or {}, False
        fields.setdefault("created_at", now)
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        cursor = self.connection.execute(f"INSERT INTO airline_news_sources ({columns}) VALUES ({placeholders})", tuple(fields.values()))
        return row_to_dict(self.connection.execute("SELECT * FROM airline_news_sources WHERE id = ?", (cursor.lastrowid,)).fetchone()) or {}, True

    def get_active_sources(self, due_only: bool = False) -> list[dict[str, Any]]:
        if due_only:
            query = """
            SELECT * FROM airline_news_sources
            WHERE is_active = 1 AND (last_checked_at IS NULL OR datetime(last_checked_at, '+' || check_interval_minutes || ' minutes') <= datetime('now'))
            ORDER BY COALESCE(last_checked_at, '1970-01-01')
            """
            return [dict(row) for row in self.connection.execute(query)]
        return [dict(row) for row in self.connection.execute("SELECT * FROM airline_news_sources WHERE is_active = 1 ORDER BY airline_name, source_role")]

    def get_by_airline(self, airline_id: int) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM airline_news_sources WHERE airline_id = ? ORDER BY source_role", (airline_id,))]

    def get_by_id(self, source_id: int) -> dict[str, Any] | None:
        return row_to_dict(self.connection.execute("SELECT * FROM airline_news_sources WHERE id = ?", (source_id,)).fetchone())

    def mark_checked(self, source_id: int, success: bool, error_message: str | None = None) -> None:
        now = utcnow_iso()
        if success:
            self.connection.execute("UPDATE airline_news_sources SET last_checked_at = ?, last_success_at = ?, last_error_message = NULL, updated_at = ? WHERE id = ?", (now, now, now, source_id))
        else:
            self.connection.execute("UPDATE airline_news_sources SET last_checked_at = ?, last_error_at = ?, last_error_message = ?, updated_at = ? WHERE id = ?", (now, now, (error_message or '')[:1000], now, source_id))

    def set_active(self, source_id: int, is_active: bool) -> None:
        self.connection.execute("UPDATE airline_news_sources SET is_active = ?, updated_at = ? WHERE id = ?", (int(is_active), utcnow_iso(), source_id))


class NewsRepository:
    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self.connection = connection or connect()

    def duplicate_exists(self, source_id: int, source_url: str, content_hash: str, external_id: str | None = None) -> bool:
        if external_id and self.connection.execute("SELECT 1 FROM airline_news WHERE source_id = ? AND external_id = ?", (source_id, external_id)).fetchone():
            return True
        return self.connection.execute("SELECT 1 FROM airline_news WHERE source_url = ? OR content_hash = ?", (source_url, content_hash)).fetchone() is not None

    def create_news(self, data: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
        if self.duplicate_exists(data["source_id"], data["source_url"], data["content_hash"], data.get("external_id")):
            logger.info("Duplicate news skipped url=%s external_id=%s", data.get("source_url"), data.get("external_id"))
            return None, False
        now = utcnow_iso()
        fields = {**data, "detected_at": data.get("detected_at") or now, "updated_at": now, "status": data.get("status") or "pending"}
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        try:
            cursor = self.connection.execute(f"INSERT INTO airline_news ({columns}) VALUES ({placeholders})", tuple(fields.values()))
        except sqlite3.IntegrityError:
            logger.info("Duplicate news skipped by DB constraint url=%s", data.get("source_url"))
            return None, False
        return self.get_by_id(int(cursor.lastrowid)), True

    def get_pending(self, limit: int = 20) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM airline_news WHERE status = 'pending' ORDER BY COALESCE(published_at, detected_at) DESC LIMIT ?", (limit,))]

    def get_by_id(self, news_id: int) -> dict[str, Any] | None:
        return row_to_dict(self.connection.execute("SELECT * FROM airline_news WHERE id = ?", (news_id,)).fetchone())

    def update_status(self, news_id: int, status: str, comment: str | None = None) -> None:
        now = utcnow_iso()
        published = now if status == "published" else None
        self.connection.execute("UPDATE airline_news SET status = ?, moderation_comment = COALESCE(?, moderation_comment), published_to_users_at = COALESCE(?, published_to_users_at), updated_at = ? WHERE id = ?", (status, comment, published, now, news_id))

    def update_parsed_fields(self, news_id: int, **fields: Any) -> None:
        fields["updated_at"] = utcnow_iso()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        self.connection.execute(f"UPDATE airline_news SET {assignments} WHERE id = ?", (*fields.values(), news_id))

    def list_published(self, category: str | None = None, airline_id: int | None = None, russian_only: bool = False, limit: int = 20) -> list[dict[str, Any]]:
        clauses = ["n.status IN ('approved', 'published')"]
        params: list[Any] = []
        if category:
            clauses.append("n.category = ?"); params.append(category)
        if airline_id:
            clauses.append("n.airline_id = ?"); params.append(airline_id)
        if russian_only:
            clauses.append("a.is_russian = 1")
        query = f"SELECT n.* FROM airline_news n JOIN airlines a ON a.id = n.airline_id WHERE {' AND '.join(clauses)} ORDER BY COALESCE(n.published_at, n.detected_at) DESC LIMIT ?"
        params.append(limit)
        return [dict(row) for row in self.connection.execute(query, tuple(params))]

    def stats(self) -> dict[str, int]:
        row = self.connection.execute("SELECT COUNT(*) total, SUM(status='pending') pending, SUM(status='published') published, SUM(status='rejected') rejected FROM airline_news").fetchone()
        stats = {key: int(row[key] or 0) for key in row.keys()} if row else {}
        stats["sources_total"] = int(self.connection.execute("SELECT COUNT(*) FROM airline_news_sources").fetchone()[0] or 0)
        stats["sources_active"] = int(self.connection.execute("SELECT COUNT(*) FROM airline_news_sources WHERE is_active = 1").fetchone()[0] or 0)
        stats["deliveries_24h"] = int(self.connection.execute("SELECT COUNT(*) FROM user_news_deliveries WHERE datetime(delivered_at) >= datetime('now', '-1 day')").fetchone()[0] or 0)
        return stats


class NewsSubscriptionRepository:
    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self.connection = connection or connect()

    def upsert_subscription(self, user_id: int, subscription_type: str, *, category: str | None = None, airline_id: int | None = None, airline_code: str | None = None, notification_mode: str = "digest_daily", is_active: bool = True) -> dict[str, Any]:
        now = utcnow_iso()
        existing = row_to_dict(self.connection.execute(
            "SELECT * FROM user_news_subscriptions WHERE user_id = ? AND subscription_type = ? AND COALESCE(category, '') = COALESCE(?, '') AND COALESCE(airline_id, 0) = COALESCE(?, 0) AND COALESCE(airline_code, '') = COALESCE(?, '')",
            (user_id, subscription_type, category, airline_id, airline_code),
        ).fetchone())
        if existing:
            self.connection.execute("UPDATE user_news_subscriptions SET notification_mode = ?, is_active = ?, updated_at = ? WHERE id = ?", (notification_mode, int(is_active), now, existing["id"]))
            return row_to_dict(self.connection.execute("SELECT * FROM user_news_subscriptions WHERE id = ?", (existing["id"],)).fetchone()) or {}
        cursor = self.connection.execute(
            "INSERT INTO user_news_subscriptions (user_id, subscription_type, category, airline_id, airline_code, notification_mode, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, subscription_type, category, airline_id, airline_code, notification_mode, int(is_active), now, now),
        )
        return row_to_dict(self.connection.execute("SELECT * FROM user_news_subscriptions WHERE id = ?", (cursor.lastrowid,)).fetchone()) or {}

    def delete_subscription(self, subscription_id: int, user_id: int | None = None) -> None:
        params: list[Any] = [subscription_id]
        clause = "id = ?"
        if user_id is not None:
            clause += " AND user_id = ?"; params.append(user_id)
        self.connection.execute(f"UPDATE user_news_subscriptions SET is_active = 0, updated_at = ? WHERE {clause}", (utcnow_iso(), *params))

    def list_user_subscriptions(self, user_id: int) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM user_news_subscriptions WHERE user_id = ? AND is_active = 1 ORDER BY subscription_type", (user_id,))]

    def record_delivery(self, user_id: int, news_id: int, delivery_type: str) -> bool:
        try:
            self.connection.execute("INSERT INTO user_news_deliveries (user_id, news_id, delivery_type, delivered_at) VALUES (?, ?, ?, ?)", (user_id, news_id, delivery_type, utcnow_iso()))
            return True
        except sqlite3.IntegrityError:
            return False


async def record_airlines_from_offers(offers: Iterable[dict[str, Any]]) -> int:
    codes = [offer.get("airline") or offer.get("airline_code") for offer in offers]
    def _record() -> int:
        with connect() as connection:
            ensure_news_schema(connection)
            changed = AirlineRepository(connection).record_ticket_airlines(codes)
            connection.commit()
            return changed
    return await asyncio.to_thread(_record)
