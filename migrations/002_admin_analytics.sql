-- Таблицы административной аналитики. Скрипт идемпотентен.
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
