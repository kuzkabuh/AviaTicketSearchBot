-- Таблица подписок на изменение цен. Скрипт идемпотентен и не меняет существующие таблицы.
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

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status
ON subscriptions(telegram_user_id, status);

CREATE INDEX IF NOT EXISTS idx_subscriptions_status_check
ON subscriptions(status, last_checked_at);

CREATE UNIQUE INDEX IF NOT EXISTS ux_active_subscription_duplicate
ON subscriptions(telegram_user_id, duplicate_key)
WHERE status = 'active';
