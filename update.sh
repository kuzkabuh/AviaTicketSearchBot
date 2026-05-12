#!/usr/bin/env bash
# ==============================================================================
# Файл: update.sh
# Версия: 1.1.0
# Описание: Безопасное обновление AviaTicketSearchBot из GitHub,
#           установка зависимостей, применение миграций БД
#           и перезапуск systemd-сервиса.
# Дата изменения: 2026-05-12
# ==============================================================================

set -Eeuo pipefail

# ------------------------------------------------------------------------------
# 1. Базовые пути и загрузка .env
# ------------------------------------------------------------------------------

PROJECT_DIR="${BOT_PROJECT_DIR:-/opt/Bots/AviaTicketSearchBot}"
ENV_FILE="$PROJECT_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

# ------------------------------------------------------------------------------
# 2. Настройки обновления
# ------------------------------------------------------------------------------

PROJECT_DIR="${BOT_PROJECT_DIR:-$PROJECT_DIR}"
BRANCH="${BOT_GIT_BRANCH:-master}"

# ВАЖНО:
# Реальное имя systemd-сервиса в проекте — avia-ticket-search-bot.service
SERVICE_NAME="${BOT_SERVICE_NAME:-avia-ticket-search-bot.service}"

LOG_PATH="${BOT_UPDATE_LOG_PATH:-$PROJECT_DIR/logs/update.log}"
LOCK_PATH="${BOT_UPDATE_LOCK_PATH:-$PROJECT_DIR/runtime/update.lock}"
STATUS_PATH="${BOT_UPDATE_STATUS_PATH:-$PROJECT_DIR/runtime/update_status.json}"

DATABASE_PATH="${DATABASE_PATH:-${DATABASE_URL:-$PROJECT_DIR/avia_bot.sqlite3}}"
DATABASE_PATH="${DATABASE_PATH#sqlite:///}"
DATABASE_PATH="${DATABASE_PATH#sqlite://}"

# Если путь к БД относительный — приводим его к абсолютному пути внутри проекта
if [[ "$DATABASE_PATH" != /* ]]; then
  DATABASE_PATH="$PROJECT_DIR/$DATABASE_PATH"
fi

# ------------------------------------------------------------------------------
# 3. Подготовка директорий и логирования
# ------------------------------------------------------------------------------

mkdir -p \
  "$(dirname "$LOG_PATH")" \
  "$(dirname "$LOCK_PATH")" \
  "$(dirname "$STATUS_PATH")"

touch "$LOG_PATH"
exec >>"$LOG_PATH" 2>&1

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

# ------------------------------------------------------------------------------
# 4. Запись статуса обновления для админ-панели
# ------------------------------------------------------------------------------

write_status() {
  local status="$1"
  local message="$2"

  STATUS_VALUE="$status" \
  STATUS_MESSAGE="$message" \
  STATUS_PATH="$STATUS_PATH" \
  python3 - <<'PY' || true
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
path.write_text(
    json.dumps(state, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
PY
}

# ------------------------------------------------------------------------------
# 5. Защита от одновременного запуска обновления
# ------------------------------------------------------------------------------

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

# ------------------------------------------------------------------------------
# 6. Универсальный запуск команд с логированием
# ------------------------------------------------------------------------------

run() {
  log "▶ $*"
  "$@"
  log "✅ $* — OK"
}

# ------------------------------------------------------------------------------
# 7. Проверка обязательных команд
# ------------------------------------------------------------------------------

check_required_commands() {
  local missing=0

  for command_name in git python3; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
      log "❌ Не найдена обязательная команда: $command_name"
      missing=1
    fi
  done

  if [[ "$missing" == "1" ]]; then
    write_status "error" "Отсутствуют обязательные системные команды"
    exit 1
  fi
}

# ------------------------------------------------------------------------------
# 8. SQL-миграции SQLite
# ------------------------------------------------------------------------------

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
  log "🗄 Путь к базе данных: $DATABASE_PATH"

  sqlite3 "$DATABASE_PATH" \
    "CREATE TABLE IF NOT EXISTS schema_migrations (
      name TEXT PRIMARY KEY,
      applied_at TEXT NOT NULL
    );"

  while IFS= read -r migration; do
    local name
    local applied

    name="$(basename "$migration")"
    applied="$(sqlite3 "$DATABASE_PATH" \
      "SELECT COUNT(*) FROM schema_migrations WHERE name = '$name';")"

    if [[ "$applied" == "0" ]]; then
      log "▶ Применяется миграция $name"

      sqlite3 "$DATABASE_PATH" < "$migration"

      sqlite3 "$DATABASE_PATH" \
        "INSERT INTO schema_migrations(name, applied_at)
         VALUES('$name', datetime('now'));"

      log "✅ Миграция $name применена"
    else
      log "ℹ️ Миграция $name уже применена"
    fi
  done < <(find "$migrations_dir" -maxdepth 1 -type f -name '*.sql' | sort)

  log "✅ SQL-миграции обработаны"
}

# ------------------------------------------------------------------------------
# 9. Перезапуск systemd-сервиса
# ------------------------------------------------------------------------------

restart_service() {
  if ! command -v systemctl >/dev/null 2>&1; then
    log "❌ systemctl не найден. Невозможно перезапустить сервис."
    return 1
  fi

  local load_state
  load_state="$(systemctl show "$SERVICE_NAME" --property=LoadState --value 2>/dev/null || true)"

  if [[ -z "$load_state" || "$load_state" == "not-found" ]]; then
    log "❌ systemd-сервис $SERVICE_NAME не найден."
    log "❌ Проверьте BOT_SERVICE_NAME в .env и реальное имя сервиса через:"
    log "   systemctl list-units --type=service | grep avia"
    return 1
  fi

  log "ℹ️ Найден systemd-сервис: $SERVICE_NAME"

  if [[ "${BOT_SERVICE_RESTART_WITH_SUDO:-true}" == "true" ]]; then
    run sudo systemctl restart "$SERVICE_NAME"
  else
    run systemctl restart "$SERVICE_NAME"
  fi

  run systemctl is-active "$SERVICE_NAME"
  log "✅ Сервис $SERVICE_NAME успешно перезапущен"
}

# ------------------------------------------------------------------------------
# 10. Основной сценарий обновления
# ------------------------------------------------------------------------------

log "============================================================"
log "🚀 Обновление AviaTicketSearchBot запущено"
log "Проект: $PROJECT_DIR"
log "Ветка: $BRANCH"
log "Сервис: $SERVICE_NAME"
log "Лог обновления: $LOG_PATH"
log "Lock-файл: $LOCK_PATH"
log "Файл статуса: $STATUS_PATH"

check_required_commands

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

# ------------------------------------------------------------------------------
# 11. Активация виртуального окружения
# ------------------------------------------------------------------------------

if [[ -f "$PROJECT_DIR/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.venv/bin/activate"
  log "✅ Виртуальное окружение активировано: $PROJECT_DIR/.venv"
else
  log "⚠️ .venv не найден, зависимости будут установлены текущим python/pip"
fi

# ------------------------------------------------------------------------------
# 12. Обновление Python-зависимостей
# ------------------------------------------------------------------------------

if [[ -f "$PROJECT_DIR/requirements.txt" ]]; then
  run python -m pip install -r "$PROJECT_DIR/requirements.txt"
else
  log "ℹ️ requirements.txt отсутствует, обновление зависимостей пропущено"
fi

# ------------------------------------------------------------------------------
# 13. Alembic-миграции, если настроены
# ------------------------------------------------------------------------------

if [[ -f "$PROJECT_DIR/alembic.ini" ]] && command -v alembic >/dev/null 2>&1; then
  run alembic upgrade head
else
  log "ℹ️ Alembic не настроен или команда alembic недоступна"
fi

# ------------------------------------------------------------------------------
# 14. SQLite-миграции и инициализация БД
# ------------------------------------------------------------------------------

apply_sqlite_migrations

run python - <<'PY'
import asyncio
import db

asyncio.run(db.init_db())
PY

# ------------------------------------------------------------------------------
# 15. Перезапуск сервиса
# ------------------------------------------------------------------------------

restart_service

# ------------------------------------------------------------------------------
# 16. Успешное завершение
# ------------------------------------------------------------------------------

log "✅ Обновление завершено успешно"
write_status "success" "Обновление успешно применено"
exit 0
