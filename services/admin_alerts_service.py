"""Centralized admin alerts with DB-backed cooldown/deduplication."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import sqlite3
from typing import Any, Protocol

from config import settings
from db import utcnow_iso

logger = logging.getLogger(__name__)

ALERT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS admin_alerts_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,
    alert_key TEXT NOT NULL,
    payload_json TEXT NULL,
    sent_at TEXT NOT NULL,
    resolved_at TEXT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_admin_alert_active
ON admin_alerts_history(alert_type, alert_key)
WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_admin_alerts_sent ON admin_alerts_history(sent_at);
"""


class BotLike(Protocol):
    async def send_message(self, chat_id: int, text: str, **kwargs: Any) -> Any: ...


def ensure_admin_alerts_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(ALERT_SCHEMA_SQL)
    existing = {row[1] for row in connection.execute("PRAGMA table_info(admin_alerts_history)").fetchall()}
    for column, definition in {
        "alert_type": "TEXT NOT NULL DEFAULT ''",
        "alert_key": "TEXT NOT NULL DEFAULT ''",
        "payload_json": "TEXT NULL",
        "sent_at": "TEXT NOT NULL DEFAULT ''",
        "resolved_at": "TEXT NULL",
        "status": "TEXT NOT NULL DEFAULT 'active'",
    }.items():
        if column not in existing:
            connection.execute(f"ALTER TABLE admin_alerts_history ADD COLUMN {column} {definition}")


class AdminAlertsService:
    def __init__(self, bot: BotLike | None = None, database_path: str | None = None) -> None:
        self.bot = bot
        self.database_path = database_path or settings.database_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        ensure_admin_alerts_schema(connection)
        return connection

    @staticmethod
    def _cooldown_passed(sent_at: str | None, cooldown_minutes: int) -> bool:
        if not sent_at:
            return True
        try:
            previous = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - previous >= timedelta(minutes=cooldown_minutes)

    def should_send(self, alert_type: str, alert_key: str, cooldown_minutes: int) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT sent_at FROM admin_alerts_history WHERE alert_type = ? AND alert_key = ? AND status = 'active' ORDER BY sent_at DESC LIMIT 1",
                (alert_type, alert_key),
            ).fetchone()
            return row is None or self._cooldown_passed(row["sent_at"], cooldown_minutes)

    def record(self, alert_type: str, alert_key: str, payload: dict[str, Any] | None = None) -> None:
        payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO admin_alerts_history(alert_type, alert_key, payload_json, sent_at, status)
                VALUES (?, ?, ?, ?, 'active')
                ON CONFLICT(alert_type, alert_key) WHERE status = 'active'
                DO UPDATE SET payload_json = excluded.payload_json, sent_at = excluded.sent_at
                """,
                (alert_type, alert_key, payload_json, utcnow_iso()),
            )
            connection.commit()

    def resolve(self, alert_type: str, alert_key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE admin_alerts_history SET status = 'resolved', resolved_at = ? WHERE alert_type = ? AND alert_key = ? AND status = 'active'",
                (utcnow_iso(), alert_type, alert_key),
            )
            connection.commit()

    async def send_alert(self, alert_type: str, alert_key: str, text: str, *, payload: dict[str, Any] | None = None, cooldown_minutes: int = 60) -> bool:
        if not self.should_send(alert_type, alert_key, cooldown_minutes):
            logger.info("Admin alert suppressed by cooldown type=%s key=%s", alert_type, alert_key)
            return False
        self.record(alert_type, alert_key, payload)
        if not self.bot or not settings.admin_telegram_ids:
            logger.warning("Admin alert recorded but not sent type=%s key=%s: bot/admin ids unavailable", alert_type, alert_key)
            return False
        for admin_id in settings.admin_telegram_ids:
            try:
                await self.bot.send_message(admin_id, text, parse_mode="HTML", disable_web_page_preview=True)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to send admin alert type=%s key=%s admin_id=%s", alert_type, alert_key, admin_id)
        return True

    async def migration_failed(self, migration_name: str, error: str) -> bool:
        return await self.send_alert("migration_failed", migration_name, f"❌ Ошибка миграции <b>{migration_name}</b>\n<code>{error[:1500]}</code>", payload={"error": error}, cooldown_minutes=60)

    async def update_failed(self, step: str, exit_code: int, tail: str) -> bool:
        return await self.send_alert("update_failed", step, f"❌ Обновление завершилось ошибкой\nШаг: <b>{step}</b>\nКод: <code>{exit_code}</code>\n\nПоследние строки лога:\n<code>{tail[:2500]}</code>", payload={"exit_code": exit_code, "tail": tail}, cooldown_minutes=30)

    async def news_pending(self, count: int) -> bool:
        return await self.send_alert("news_pending", "moderation_queue", f"📰 Найдено {count} новых новостей, требуется модерация", payload={"count": count}, cooldown_minutes=60)

    async def news_source_broken(self, source: dict[str, Any]) -> bool:
        key = str(source.get("id") or source.get("source_url") or "unknown")
        text = f"⚠️ Не удалось получить новости с источника <b>{source.get('airline_name', '—')}</b> {source.get('consecutive_errors', 0)} раза подряд\n{source.get('source_url', '')}\n<code>{str(source.get('last_error_message') or '')[:1000]}</code>"
        return await self.send_alert("news_source_broken", key, text, payload=source, cooldown_minutes=180)

    async def news_source_recovered(self, source: dict[str, Any]) -> bool:
        key = str(source.get("id") or source.get("source_url") or "unknown")
        self.resolve("news_source_broken", key)
        return await self.send_alert("news_source_recovered", key, f"✅ Источник <b>{source.get('airline_name', '—')}</b> снова работает\n{source.get('source_url', '')}", payload=source, cooldown_minutes=60)


async def notify_admins(bot: BotLike | None, alert_type: str, alert_key: str, text: str, **kwargs: Any) -> bool:
    return await AdminAlertsService(bot).send_alert(alert_type, alert_key, text, **kwargs)
