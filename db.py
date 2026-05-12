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
"""


async def init_db() -> None:
    """Создает таблицы и индексы, не ломая существующую схему."""
    def _init() -> None:
        with sqlite3.connect(settings.database_path) as connection:
            connection.executescript(SCHEMA_SQL)
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
