-- Handled idempotently by scripts/run_migrations.py; do not execute ALTER blindly.
-- Добавляет целевую цену для режима уведомлений ниже заданной суммы.
-- Безопасно для существующих данных: для старых подписок значение остается NULL.
ALTER TABLE subscriptions
ADD COLUMN target_price INTEGER;
