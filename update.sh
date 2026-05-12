#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${BOT_PROJECT_DIR:-/opt/Bots/AviaTicketSearchBot}"
ENV_FILE="$PROJECT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

PROJECT_DIR="${BOT_PROJECT_DIR:-$PROJECT_DIR}"
BRANCH="${BOT_GIT_BRANCH:-master}"
SERVICE_NAME="${BOT_SERVICE_NAME:-avia-ticket-bot.service}"
LOG_PATH="${BOT_UPDATE_LOG_PATH:-$PROJECT_DIR/logs/update.log}"
LOCK_PATH="${BOT_UPDATE_LOCK_PATH:-$PROJECT_DIR/runtime/update.lock}"
STATUS_PATH="${BOT_UPDATE_STATUS_PATH:-$PROJECT_DIR/runtime/update_status.json}"
DATABASE_PATH="${DATABASE_PATH:-${DATABASE_URL:-$PROJECT_DIR/avia_bot.sqlite3}}"
DATABASE_PATH="${DATABASE_PATH#sqlite:///}"
DATABASE_PATH="${DATABASE_PATH#sqlite://}"

mkdir -p "$(dirname "$LOG_PATH")" "$(dirname "$LOCK_PATH")" "$(dirname "$STATUS_PATH")"

touch "$LOG_PATH"
exec >>"$LOG_PATH" 2>&1

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

write_status() {
  local status="$1"
  local message="$2"
  STATUS_VALUE="$status" STATUS_MESSAGE="$message" STATUS_PATH="$STATUS_PATH" python3 - <<'PY' || true
from datetime import datetime, timezone
import json
import os
from pathlib import Path

path = Path(os.environ["STATUS_PATH"])
try:
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
except (OSError, json.JSONDecodeError):
    state = {}
state["status"] = os.environ["STATUS_VALUE"]
state["message"] = os.environ["STATUS_MESSAGE"]
state["finished_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
state["notified"] = False
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
PY
}

if ! mkdir "$LOCK_PATH" 2>/dev/null; then
  log "⚠️ Обновление уже выполняется: lock $LOCK_PATH существует"
  write_status "error" "Обновление уже выполняется"
  exit 1
fi

cleanup() {
  rm -rf "$LOCK_PATH"
}
trap cleanup EXIT

on_error() {
  local exit_code=$?
  log "❌ Обновление завершилось ошибкой. Код: $exit_code"
  write_status "error" "Ошибка обновления, код $exit_code"
  exit "$exit_code"
}
trap on_error ERR

run() {
  log "▶ $*"
  "$@"
  log "✅ $* — OK"
}

apply_sqlite_migrations() {
  local migrations_dir="$PROJECT_DIR/migrations"
  if [[ ! -d "$migrations_dir" ]]; then
    log "ℹ️ Каталог migrations отсутствует, SQL-миграции пропущены"
    return 0
  fi
  if ! command -v sqlite3 >/dev/null 2>&1; then
    log "⚠️ sqlite3 не найден, SQL-миграции пропущены"
    return 0
  fi

  log "▶ Применение SQL-миграций из $migrations_dir"
  sqlite3 "$DATABASE_PATH" "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL);"
  while IFS= read -r migration; do
    local name
    name="$(basename "$migration")"
    local applied
    applied="$(sqlite3 "$DATABASE_PATH" "SELECT COUNT(*) FROM schema_migrations WHERE name = '$name';")"
    if [[ "$applied" == "0" ]]; then
      log "▶ Применяется миграция $name"
      sqlite3 "$DATABASE_PATH" < "$migration"
      sqlite3 "$DATABASE_PATH" "INSERT INTO schema_migrations(name, applied_at) VALUES('$name', datetime('now'));"
      log "✅ Миграция $name применена"
    else
      log "ℹ️ Миграция $name уже применена"
    fi
  done < <(find "$migrations_dir" -maxdepth 1 -type f -name '*.sql' | sort)
  log "✅ SQL-миграции обработаны"
}

restart_service() {
  if command -v systemctl >/dev/null 2>&1; then
    if systemctl list-unit-files "$SERVICE_NAME" >/dev/null 2>&1; then
      if [[ "${BOT_SERVICE_RESTART_WITH_SUDO:-true}" == "true" ]]; then
        run sudo systemctl restart "$SERVICE_NAME"
      else
        run systemctl restart "$SERVICE_NAME"
      fi
      run systemctl is-active "$SERVICE_NAME"
      return 0
    fi
  fi
  log "⚠️ systemd-сервис $SERVICE_NAME недоступен. Перезапуск пропущен."
}

log "============================================================"
log "🚀 Обновление AviaTicketSearchBot запущено"
log "Проект: $PROJECT_DIR"
log "Ветка: $BRANCH"
log "Сервис: $SERVICE_NAME"

cd "$PROJECT_DIR"

BEFORE_COMMIT="$(git rev-parse --short HEAD)"
log "Текущий commit до обновления: $BEFORE_COMMIT"

run git fetch origin "$BRANCH"
COMMITS_BEHIND="$(git rev-list --count "HEAD..origin/$BRANCH")"
if [[ "$COMMITS_BEHIND" == "0" ]]; then
  log "✅ Обновления не найдены. Установлена актуальная версия бота."
  write_status "no_updates" "Обновления не найдены"
  exit 0
fi

log "🆕 Найдены новые изменения. Доступно коммитов: $COMMITS_BEHIND"
run git pull --ff-only origin "$BRANCH"
AFTER_COMMIT="$(git rev-parse --short HEAD)"
log "Commit после обновления: $AFTER_COMMIT"

if [[ -f "$PROJECT_DIR/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.venv/bin/activate"
  log "✅ Виртуальное окружение активировано: $PROJECT_DIR/.venv"
else
  log "⚠️ .venv не найден, зависимости будут установлены текущим python/pip"
fi

if [[ -f "$PROJECT_DIR/requirements.txt" ]]; then
  run python -m pip install -r "$PROJECT_DIR/requirements.txt"
else
  log "ℹ️ requirements.txt отсутствует, обновление зависимостей пропущено"
fi

if [[ -f "$PROJECT_DIR/alembic.ini" ]] && command -v alembic >/dev/null 2>&1; then
  run alembic upgrade head
else
  log "ℹ️ Alembic не настроен или команда alembic недоступна"
fi
apply_sqlite_migrations
run python - <<'PY'
import asyncio
import db

asyncio.run(db.init_db())
PY

restart_service

log "✅ Обновление завершено успешно"
write_status "success" "Обновление успешно применено"
exit 0
