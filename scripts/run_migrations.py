"""Idempotent SQLite migration runner for update.sh and tests.

The runner records SQL migrations in schema_migrations only after a successful
transaction. It also repairs legacy partially-applied migrations whose expected
schema changes are already present, so duplicate-column failures do not block
updates.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys
from typing import Callable


@dataclass(frozen=True)
class MigrationPrecheck:
    table: str
    columns: tuple[str, ...] = ()
    indexes: tuple[str, ...] = ()


def _has_columns(connection: sqlite3.Connection, table: str, columns: tuple[str, ...]) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    if not rows:
        return False
    existing = {row[1] for row in rows}
    return all(column in existing for column in columns)


def _has_indexes(connection: sqlite3.Connection, indexes: tuple[str, ...]) -> bool:
    if not indexes:
        return True
    placeholders = ",".join("?" for _ in indexes)
    rows = connection.execute(
        f"SELECT name FROM sqlite_master WHERE type='index' AND name IN ({placeholders})",
        indexes,
    ).fetchall()
    return {row[0] for row in rows} >= set(indexes)


MIGRATION_PRECHECKS: dict[str, MigrationPrecheck] = {
    "001_create_subscriptions.sql": MigrationPrecheck("subscriptions"),
    "002_admin_analytics.sql": MigrationPrecheck("users"),
    "003_subscription_notification_mode.sql": MigrationPrecheck("subscriptions", ("notification_mode",)),
    "004_subscription_target_price.sql": MigrationPrecheck("subscriptions", ("target_price",)),
    "005_user_locale_currency.sql": MigrationPrecheck("users", ("language_code", "currency_code", "market_code")),
}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_bookkeeping(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'applied',
            note TEXT NULL
        )
        """
    )
    existing = {row[1] for row in connection.execute("PRAGMA table_info(schema_migrations)").fetchall()}
    if "status" not in existing:
        connection.execute("ALTER TABLE schema_migrations ADD COLUMN status TEXT NOT NULL DEFAULT 'applied'")
    if "note" not in existing:
        connection.execute("ALTER TABLE schema_migrations ADD COLUMN note TEXT NULL")


def mark_applied(connection: sqlite3.Connection, name: str, note: str = "applied") -> None:
    connection.execute(
        """
        INSERT INTO schema_migrations(name, applied_at, status, note)
        VALUES (?, ?, 'applied', ?)
        ON CONFLICT(name) DO UPDATE SET
            applied_at = excluded.applied_at,
            status = 'applied',
            note = excluded.note
        """,
        (name, utcnow_iso(), note),
    )


def already_recorded(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM schema_migrations WHERE name = ? AND status = 'applied'",
        (name,),
    ).fetchone()
    return row is not None


def structurally_applied(connection: sqlite3.Connection, name: str) -> bool:
    precheck = MIGRATION_PRECHECKS.get(name)
    if precheck is None:
        return False
    return _has_columns(connection, precheck.table, precheck.columns) and _has_indexes(connection, precheck.indexes)


def apply_migrations(database_path: Path, migrations_dir: Path, log: Callable[[str], None] = print) -> None:
    if not migrations_dir.exists():
        log(f"ℹ️ Каталог миграций не найден: {migrations_dir}")
        return
    migrations = sorted(migrations_dir.glob("*.sql"))
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        ensure_bookkeeping(connection)
        connection.commit()
        for migration in migrations:
            name = migration.name
            if already_recorded(connection, name):
                log(f"ℹ️ Миграция {name} уже применена")
                continue
            if structurally_applied(connection, name):
                mark_applied(connection, name, "recovered: expected schema already exists")
                connection.commit()
                log(f"✅ Миграция {name} отмечена применённой: структура уже существует")
                continue
            sql = migration.read_text(encoding="utf-8").strip()
            if not sql:
                mark_applied(connection, name, "empty migration")
                connection.commit()
                log(f"✅ Пустая миграция {name} отмечена применённой")
                continue
            log(f"▶ Применяется миграция {name}")
            try:
                connection.execute("BEGIN")
                connection.executescript(sql)
                mark_applied(connection, name)
                connection.commit()
                log(f"✅ Миграция {name} применена")
            except sqlite3.Error as error:
                connection.rollback()
                if structurally_applied(connection, name):
                    mark_applied(connection, name, f"recovered after sqlite error: {error}")
                    connection.commit()
                    log(f"✅ Миграция {name} восстановлена после ошибки SQLite: {error}")
                    continue
                log(f"❌ Ошибка миграции {name}: {error}")
                raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run idempotent SQLite migrations")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--migrations-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    apply_migrations(args.database, args.migrations_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
