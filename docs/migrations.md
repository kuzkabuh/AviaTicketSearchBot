# Безопасные SQLite-миграции

Миграции применяются скриптом `scripts/run_migrations.py`, который вызывается из `update.sh`.

## Принципы

- `schema_migrations` создаётся автоматически.
- Запись о миграции добавляется только после успешного выполнения транзакции.
- Повторный запуск безопасен: уже применённые миграции пропускаются.
- Частично применённые legacy-миграции восстанавливаются структурной проверкой через `PRAGMA table_info`.
- Колонки `subscriptions.notification_mode`, `subscriptions.target_price` и `users.language_code/currency_code/market_code` не добавляются без проверки существования.

## Ошибка `duplicate column name: notification_mode`

Причина: старая версия приложения уже добавляла `notification_mode` через runtime repair в `db._repair_schema`, но `update.sh` считал SQL-файл `003_subscription_notification_mode.sql` неприменённым, потому что записи в `schema_migrations` не было. Старый runner безусловно выполнял `ALTER TABLE subscriptions ADD COLUMN notification_mode ...`, и SQLite падал.

Исправление: runner перед выполнением 003 проверяет `PRAGMA table_info(subscriptions)`. Если колонка уже есть, миграция помечается как применённая с note `recovered: expected schema already exists`.

## Ручная проверка

```bash
PYTHONPATH=. python scripts/run_migrations.py --database /path/to/avia_bot.sqlite3 --migrations-dir migrations
PYTHONPATH=. python scripts/run_migrations.py --database /path/to/avia_bot.sqlite3 --migrations-dir migrations
```

Второй запуск должен завершиться без `duplicate column`, `table already exists` и `index already exists`.
