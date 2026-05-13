-- Добавляет режим уведомлений для подписок.
-- Безопасно для существующих данных: старые подписки получают режим по умолчанию.
ALTER TABLE subscriptions
ADD COLUMN notification_mode TEXT NOT NULL DEFAULT 'any_change';
