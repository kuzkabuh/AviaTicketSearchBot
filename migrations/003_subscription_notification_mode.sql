-- Handled idempotently by scripts/run_migrations.py; do not execute ALTER blindly.
-- Добавляет режим уведомлений для подписок.
-- Безопасно для существующих данных: старые подписки получают режим по умолчанию.
ALTER TABLE subscriptions
ADD COLUMN notification_mode TEXT NOT NULL DEFAULT 'any_change';
