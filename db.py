"""SQLite-хранилище подписок на изменение цен."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import sqlite3
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

ACTIVE = "active"
DISABLED = "disabled"
DELETED = "deleted"


def utcnow_iso() -> str:
    """Возвращает текущий UTC timestamp в ISO-формате."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    telegram_username TEXT,
    origin_city TEXT NOT NULL,
    origin_airport TEXT NOT NULL,
    origin_code TEXT NOT NULL,
    destination_city TEXT NOT NULL,
    destination_airport TEXT NOT NULL,
    destination_code TEXT NOT NULL,
    departure_date TEXT NOT NULL,
    passengers INTEGER NOT NULL,
    airline TEXT,
    flight_number TEXT,
    departure_time TEXT,
    arrival_time TEXT,
    duration INTEGER,
    transfers INTEGER,
    initial_price REAL,
    last_price REAL,
    currency TEXT NOT NULL,
    purchase_link TEXT,
    offer_id TEXT,
    created_at TEXT NOT NULL,
    last_checked_at TEXT,
    last_notified_at TEXT,
    not_found_notified_at TEXT,
    failed_checks INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    duplicate_key TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status ON subscriptions(telegram_user_id, status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status_check ON subscriptions(status, last_checked_at);
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_subscription_duplicate
ON subscriptions(telegram_user_id, duplicate_key)
WHERE status = 'active';

CREATE TABLE IF NOT EXISTS users (
    telegram_user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    created_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_last_activity_at ON users(last_activity_at);

CREATE TABLE IF NOT EXISTS bot_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER,
    event_type TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bot_events_type_created ON bot_events(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_bot_events_user_created ON bot_events(telegram_user_id, created_at);

CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER,
    origin_code TEXT NOT NULL,
    destination_code TEXT NOT NULL,
    departure_date TEXT NOT NULL,
    passengers INTEGER NOT NULL,
    results_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_search_history_created_at ON search_history(created_at);
CREATE INDEX IF NOT EXISTS idx_search_history_route_created ON search_history(origin_code, destination_code, created_at);
"""


USER_COLUMNS: dict[str, str] = {
    "username": "TEXT",
    "first_name": "TEXT",
    "last_name": "TEXT",
    "created_at": "TEXT NOT NULL DEFAULT ''",
    "last_activity_at": "TEXT NOT NULL DEFAULT ''",
}

SEARCH_HISTORY_COLUMNS: dict[str, str] = {
    "telegram_user_id": "INTEGER",
    "origin_code": "TEXT NOT NULL DEFAULT '—'",
    "destination_code": "TEXT NOT NULL DEFAULT '—'",
    "departure_date": "TEXT NOT NULL DEFAULT '—'",
    "passengers": "INTEGER NOT NULL DEFAULT 1",
    "results_count": "INTEGER NOT NULL DEFAULT 0",
    "status": "TEXT NOT NULL DEFAULT 'unknown'",
    "created_at": "TEXT NOT NULL DEFAULT ''",
}

BOT_EVENT_COLUMNS: dict[str, str] = {
    "telegram_user_id": "INTEGER",
    "event_type": "TEXT NOT NULL DEFAULT 'unknown'",
    "details": "TEXT",
    "created_at": "TEXT NOT NULL DEFAULT ''",
}


SUBSCRIPTION_COLUMNS: dict[str, str] = {
    "telegram_username": "TEXT",
    "origin_city": "TEXT NOT NULL DEFAULT '—'",
    "origin_airport": "TEXT NOT NULL DEFAULT '—'",
    "origin_code": "TEXT NOT NULL DEFAULT '—'",
    "destination_city": "TEXT NOT NULL DEFAULT '—'",
    "destination_airport": "TEXT NOT NULL DEFAULT '—'",
    "destination_code": "TEXT NOT NULL DEFAULT '—'",
    "departure_date": "TEXT NOT NULL DEFAULT '—'",
    "passengers": "INTEGER NOT NULL DEFAULT 1",
    "airline": "TEXT",
    "flight_number": "TEXT",
    "departure_time": "TEXT",
    "arrival_time": "TEXT",
    "duration": "INTEGER",
    "transfers": "INTEGER",
    "initial_price": "REAL",
    "last_price": "REAL",
    "currency": "TEXT NOT NULL DEFAULT 'RUB'",
    "purchase_link": "TEXT",
    "offer_id": "TEXT",
    "created_at": "TEXT NOT NULL DEFAULT ''",
    "last_checked_at": "TEXT",
    "last_notified_at": "TEXT",
    "not_found_notified_at": "TEXT",
    "failed_checks": "INTEGER NOT NULL DEFAULT 0",
    "status": "TEXT NOT NULL DEFAULT 'active'",
    "duplicate_key": "TEXT NOT NULL DEFAULT ''",
}


def _ensure_columns(connection: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    """Добавляет недостающие колонки после обновления старой SQLite-схемы."""
    existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    for column, definition in columns.items():
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            logger.info("Added missing column %s.%s", table, column)


def _repair_schema(connection: sqlite3.Connection) -> None:
    """Доводит старые базы до текущей структуры без отдельного Alembic."""
    _ensure_columns(connection, "subscriptions", SUBSCRIPTION_COLUMNS)
    _ensure_columns(connection, "users", USER_COLUMNS)
    _ensure_columns(connection, "search_history", SEARCH_HISTORY_COLUMNS)
    _ensure_columns(connection, "bot_events", BOT_EVENT_COLUMNS)
    connection.execute(
        """
        UPDATE subscriptions
        SET duplicate_key = origin_code || ':' || destination_code || ':' || departure_date || ':' || passengers || ':' || COALESCE(offer_id, airline, flight_number, '')
        WHERE duplicate_key = '' OR duplicate_key IS NULL
        """
    )


async def init_db() -> None:
    """Создает таблицы/индексы и ремонтирует старую схему SQLite."""
    def _init() -> None:
        with sqlite3.connect(settings.database_path) as connection:
            connection.executescript(SCHEMA_SQL)
            _repair_schema(connection)
            connection.commit()

    await asyncio.to_thread(_init)
    logger.info("Database initialized: %s", settings.database_path)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    return connection


def make_duplicate_key(offer: dict[str, Any], passengers: int) -> str:
    """Формирует ключ дубля активной подписки."""
    if offer.get("offer_id"):
        flight_part = str(offer["offer_id"])
    else:
        flight_part = ":".join(
            str(offer.get(field) or "")
            for field in ("airline", "flight_number", "departure_time", "arrival_time")
        )
    return ":".join(
        [
            str(offer.get("origin") or ""),
            str(offer.get("destination") or ""),
            str(offer.get("date") or ""),
            str(passengers),
            flight_part,
        ]
    )


async def create_subscription(telegram_user_id: int, telegram_username: str | None, offer: dict[str, Any], passengers: int) -> tuple[bool, dict[str, Any] | None]:
    """Создает подписку или возвращает признак дубля."""
    duplicate_key = make_duplicate_key(offer, passengers)
    now = utcnow_iso()

    row = {
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
        "origin_city": offer.get("origin_city") or offer.get("origin") or "—",
        "origin_airport": offer.get("origin_airport") or offer.get("origin") or "—",
        "origin_code": offer.get("origin") or "—",
        "destination_city": offer.get("destination_city") or offer.get("destination") or "—",
        "destination_airport": offer.get("destination_airport") or offer.get("destination") or "—",
        "destination_code": offer.get("destination") or "—",
        "departure_date": offer.get("date") or "—",
        "passengers": passengers,
        "airline": offer.get("airline"),
        "flight_number": offer.get("flight_number"),
        "departure_time": offer.get("departure_time"),
        "arrival_time": offer.get("arrival_time"),
        "duration": offer.get("duration"),
        "transfers": offer.get("transfers"),
        "initial_price": offer.get("price"),
        "last_price": offer.get("price"),
        "currency": offer.get("currency") or "RUB",
        "purchase_link": offer.get("link"),
        "offer_id": offer.get("offer_id"),
        "created_at": now,
        "last_checked_at": None,
        "last_notified_at": None,
        "not_found_notified_at": None,
        "failed_checks": 0,
        "status": ACTIVE,
        "duplicate_key": duplicate_key,
    }

    def _insert() -> tuple[bool, dict[str, Any] | None]:
        placeholders = ", ".join("?" for _ in row)
        columns = ", ".join(row)
        try:
            with _connect() as connection:
                cursor = connection.execute(f"INSERT INTO subscriptions ({columns}) VALUES ({placeholders})", tuple(row.values()))
                connection.commit()
                created = get_subscription_sync(cursor.lastrowid)
                return True, created
        except sqlite3.IntegrityError:
            return False, None

    return await asyncio.to_thread(_insert)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def get_subscription_sync(subscription_id: int) -> dict[str, Any] | None:
    """Синхронно получает подписку внутри DB thread."""
    with _connect() as connection:
        return _row_to_dict(connection.execute("SELECT * FROM subscriptions WHERE id = ?", (subscription_id,)).fetchone())


async def get_subscription(subscription_id: int) -> dict[str, Any] | None:
    """Получает подписку по id."""
    return await asyncio.to_thread(get_subscription_sync, subscription_id)


async def list_active_subscriptions(telegram_user_id: int | None = None) -> list[dict[str, Any]]:
    """Возвращает активные подписки всех пользователей или одного пользователя."""
    def _list() -> list[dict[str, Any]]:
        with _connect() as connection:
            if telegram_user_id is None:
                rows = connection.execute("SELECT * FROM subscriptions WHERE status = ? ORDER BY created_at", (ACTIVE,)).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM subscriptions WHERE telegram_user_id = ? AND status = ? ORDER BY created_at",
                    (telegram_user_id, ACTIVE),
                ).fetchall()
            return [dict(row) for row in rows]

    return await asyncio.to_thread(_list)


async def update_subscription(subscription_id: int, **fields: Any) -> None:
    """Обновляет произвольные поля подписки."""
    if not fields:
        return

    def _update() -> None:
        assignments = ", ".join(f"{field} = ?" for field in fields)
        values = [*fields.values(), subscription_id]
        with _connect() as connection:
            connection.execute(f"UPDATE subscriptions SET {assignments} WHERE id = ?", values)
            connection.commit()

    await asyncio.to_thread(_update)


async def mark_subscription_deleted(subscription_id: int, telegram_user_id: int) -> bool:
    """Мягко удаляет подписку пользователя."""
    now = utcnow_iso()

    def _delete() -> bool:
        with _connect() as connection:
            cursor = connection.execute(
                "UPDATE subscriptions SET status = ?, last_checked_at = ? WHERE id = ? AND telegram_user_id = ? AND status = ?",
                (DELETED, now, subscription_id, telegram_user_id, ACTIVE),
            )
            connection.commit()
            return cursor.rowcount > 0

    return await asyncio.to_thread(_delete)


async def upsert_user(
    telegram_user_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> None:
    """Создает пользователя или обновляет его последнюю активность."""
    now = utcnow_iso()

    def _upsert() -> None:
        with _connect() as connection:
            connection.execute(
                """
                INSERT INTO users (telegram_user_id, username, first_name, last_name, created_at, last_activity_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    last_activity_at = excluded.last_activity_at
                """,
                (telegram_user_id, username, first_name, last_name, now, now),
            )
            connection.commit()

    await asyncio.to_thread(_upsert)


async def record_bot_event(telegram_user_id: int | None, event_type: str, details: str | None = None) -> None:
    """Сохраняет событие использования для аналитики."""
    now = utcnow_iso()

    def _insert() -> None:
        with _connect() as connection:
            connection.execute(
                "INSERT INTO bot_events (telegram_user_id, event_type, details, created_at) VALUES (?, ?, ?, ?)",
                (telegram_user_id, event_type, details, now),
            )
            connection.commit()

    await asyncio.to_thread(_insert)


async def record_search_history(
    telegram_user_id: int | None,
    origin_code: str,
    destination_code: str,
    departure_date: str,
    passengers: int,
    results_count: int,
    status: str,
) -> None:
    """Сохраняет историю поиска билетов."""
    now = utcnow_iso()

    def _insert() -> None:
        with _connect() as connection:
            connection.execute(
                """
                INSERT INTO search_history
                (telegram_user_id, origin_code, destination_code, departure_date, passengers, results_count, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (telegram_user_id, origin_code, destination_code, departure_date, passengers, results_count, status, now),
            )
            connection.commit()

    await asyncio.to_thread(_insert)


def _period_condition(days: int | None, column: str = "created_at") -> tuple[str, tuple[str, ...]]:
    if days is None:
        return "", ()
    if days == 0:
        return f" AND date({column}) = date('now')", ()
    return f" AND datetime({column}) >= datetime('now', ?)", (f"-{days} days",)


def _scalar(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> int:
    value = connection.execute(query, params).fetchone()[0]
    return int(value or 0)


async def get_overview_stats() -> dict[str, int]:
    """Возвращает общую статистику использования."""
    def _stats() -> dict[str, int]:
        with _connect() as connection:
            return {
                "users_total": _scalar(connection, "SELECT COUNT(*) FROM users"),
                "users_active_24h": _scalar(connection, "SELECT COUNT(*) FROM users WHERE datetime(last_activity_at) >= datetime('now', '-1 day')"),
                "users_active_7d": _scalar(connection, "SELECT COUNT(*) FROM users WHERE datetime(last_activity_at) >= datetime('now', '-7 days')"),
                "users_active_30d": _scalar(connection, "SELECT COUNT(*) FROM users WHERE datetime(last_activity_at) >= datetime('now', '-30 days')"),
                "searches_total": _scalar(connection, "SELECT COUNT(*) FROM search_history"),
                "searches_today": _scalar(connection, "SELECT COUNT(*) FROM search_history WHERE date(created_at) = date('now')"),
                "searches_7d": _scalar(connection, "SELECT COUNT(*) FROM search_history WHERE datetime(created_at) >= datetime('now', '-7 days')"),
                "subscriptions_total": _scalar(connection, "SELECT COUNT(*) FROM subscriptions"),
                "subscriptions_active": _scalar(connection, "SELECT COUNT(*) FROM subscriptions WHERE status = ?", (ACTIVE,)),
                "subscriptions_inactive": _scalar(connection, "SELECT COUNT(*) FROM subscriptions WHERE status != ?", (ACTIVE,)),
                "price_notifications": _scalar(connection, "SELECT COUNT(*) FROM bot_events WHERE event_type IN ('price_notification_up', 'price_notification_down')"),
                "price_checks_success": _scalar(connection, "SELECT COUNT(*) FROM bot_events WHERE event_type IN ('price_check_success', 'price_changed')"),
                "price_checks_errors": _scalar(connection, "SELECT COUNT(*) FROM bot_events WHERE event_type IN ('price_check_error', 'api_error', 'flight_not_found')"),
            }
    return await asyncio.to_thread(_stats)


async def get_period_stats(days: int | None) -> dict[str, int]:
    """Возвращает статистику за период."""
    condition, params = _period_condition(days)
    def _stats() -> dict[str, int]:
        with _connect() as connection:
            return {
                "new_users": _scalar(connection, f"SELECT COUNT(*) FROM users WHERE 1=1{condition}", params),
                "searches": _scalar(connection, f"SELECT COUNT(*) FROM search_history WHERE 1=1{condition}", params),
                "subscriptions_created": _scalar(connection, f"SELECT COUNT(*) FROM subscriptions WHERE 1=1{condition}", params),
                "notifications": _scalar(connection, f"SELECT COUNT(*) FROM bot_events WHERE event_type IN ('price_notification_up', 'price_notification_down'){condition}", params),
                "errors": _scalar(connection, f"SELECT COUNT(*) FROM bot_events WHERE event_type IN ('price_check_error', 'api_error', 'flight_not_found'){condition}", params),
            }
    return await asyncio.to_thread(_stats)


async def get_popular_routes(days: int | None = 30, limit: int = 10) -> list[dict[str, Any]]:
    condition, params = _period_condition(days)
    def _routes() -> list[dict[str, Any]]:
        with _connect() as connection:
            rows = connection.execute(
                f"""
                SELECT origin_code, destination_code, COUNT(*) AS count
                FROM search_history
                WHERE 1=1{condition}
                GROUP BY origin_code, destination_code
                ORDER BY count DESC, origin_code, destination_code
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
            return [dict(row) for row in rows]
    return await asyncio.to_thread(_routes)


async def get_popular_cities(kind: str, days: int | None = 30, limit: int = 5) -> list[dict[str, Any]]:
    column = "origin_code" if kind == "origin" else "destination_code"
    condition, params = _period_condition(days)
    def _cities() -> list[dict[str, Any]]:
        with _connect() as connection:
            rows = connection.execute(
                f"SELECT {column} AS code, COUNT(*) AS count FROM search_history WHERE 1=1{condition} GROUP BY {column} ORDER BY count DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
            return [dict(row) for row in rows]
    return await asyncio.to_thread(_cities)


async def get_subscription_analytics() -> dict[str, float | int]:
    """Возвращает аналитику подписок."""
    def _stats() -> dict[str, float | int]:
        with _connect() as connection:
            active = _scalar(connection, "SELECT COUNT(*) FROM subscriptions WHERE status = ?", (ACTIVE,))
            users_with_active = _scalar(connection, "SELECT COUNT(DISTINCT telegram_user_id) FROM subscriptions WHERE status = ?", (ACTIVE,))
            return {
                "total": _scalar(connection, "SELECT COUNT(*) FROM subscriptions"),
                "active": active,
                "inactive": _scalar(connection, "SELECT COUNT(*) FROM subscriptions WHERE status != ?", (ACTIVE,)),
                "avg_active_per_user": active / users_with_active if users_with_active else 0.0,
                "price_down_notifications": _scalar(connection, "SELECT COUNT(*) FROM bot_events WHERE event_type = 'price_notification_down'"),
                "price_up_notifications": _scalar(connection, "SELECT COUNT(*) FROM bot_events WHERE event_type = 'price_notification_up'"),
                "not_found_checks": _scalar(connection, "SELECT COUNT(*) FROM bot_events WHERE event_type = 'flight_not_found'"),
            }
    return await asyncio.to_thread(_stats)


async def get_users_summary() -> dict[str, int]:
    """Возвращает сводку по пользователям."""
    def _stats() -> dict[str, int]:
        with _connect() as connection:
            return {
                "total": _scalar(connection, "SELECT COUNT(*) FROM users"),
                "new_today": _scalar(connection, "SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')"),
                "active_7d": _scalar(connection, "SELECT COUNT(*) FROM users WHERE datetime(last_activity_at) >= datetime('now', '-7 days')"),
                "with_active_subscriptions": _scalar(connection, "SELECT COUNT(DISTINCT telegram_user_id) FROM subscriptions WHERE status = ?", (ACTIVE,)),
            }
    return await asyncio.to_thread(_stats)


async def list_all_user_ids() -> list[int]:
    """Возвращает Telegram ID всех известных пользователей для админской рассылки."""
    def _users() -> list[int]:
        with _connect() as connection:
            rows = connection.execute("SELECT telegram_user_id FROM users ORDER BY created_at").fetchall()
            return [int(row["telegram_user_id"]) for row in rows]
    return await asyncio.to_thread(_users)


async def get_latest_users(limit: int = 10) -> list[dict[str, Any]]:
    """Возвращает последних зарегистрированных пользователей."""
    def _users() -> list[dict[str, Any]]:
        with _connect() as connection:
            rows = connection.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(row) for row in rows]
    return await asyncio.to_thread(_users)


async def get_users_with_active_subscriptions(limit: int = 10) -> list[dict[str, Any]]:
    """Возвращает пользователей с наибольшим числом активных подписок."""
    def _users() -> list[dict[str, Any]]:
        with _connect() as connection:
            rows = connection.execute(
                """
                SELECT s.telegram_user_id, COALESCE(u.username, s.telegram_username) AS username, COUNT(*) AS active_subscriptions
                FROM subscriptions s
                LEFT JOIN users u ON u.telegram_user_id = s.telegram_user_id
                WHERE s.status = ?
                GROUP BY s.telegram_user_id, username
                ORDER BY active_subscriptions DESC
                LIMIT ?
                """,
                (ACTIVE, limit),
            ).fetchall()
            return [dict(row) for row in rows]
    return await asyncio.to_thread(_users)


async def count_active_subscriptions() -> int:
    """Считает активные подписки."""
    def _count() -> int:
        with _connect() as connection:
            return _scalar(connection, "SELECT COUNT(*) FROM subscriptions WHERE status = ?", (ACTIVE,))
    return await asyncio.to_thread(_count)


async def check_database_status() -> str:
    """Проверяет доступность SQLite-БД."""
    def _check() -> str:
        try:
            with _connect() as connection:
                connection.execute("SELECT 1").fetchone()
            return "доступна"
        except sqlite3.Error as error:
            return f"ошибка: {error}"
    return await asyncio.to_thread(_check)
