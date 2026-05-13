# Процесс обновления

`update.sh` выполняется с `set -Eeuo pipefail` и пишет лог в `BOT_UPDATE_LOG_PATH`.

Этапы:

1. загрузка `.env`;
2. проверка Git-репозитория и `safe.directory`;
3. `git fetch` и `git pull --ff-only`;
4. установка зависимостей из `requirements.txt`;
5. Alembic, если он настроен;
6. безопасные SQLite-миграции через `scripts/run_migrations.py`;
7. `db.init_db()` для runtime repair старых production-баз;
8. restart systemd-сервиса;
9. запись результата в `runtime/update_status.json`.

Если обновление падает, статус становится `error`, лог содержит шаг и код ошибки. После рестарта бот читает статус и отправляет администратору уведомление с последними строками лога.
