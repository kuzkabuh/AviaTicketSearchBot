#!/usr/bin/env bash
# ==============================================================================
# Файл: update.sh
# Описание: безопасное обновление AviaTicketSearchBot из GitHub с логированием,
#           миграциями SQLite и перезапуском systemd-сервиса после успешного pull.
# ==============================================================================

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="${BOT_PROJECT_DIR:-$SCRIPT_DIR}"
ENV_FILE="$PROJECT_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

PROJECT_DIR="${BOT_PROJECT_DIR:-$PROJECT_DIR}"
BRANCH="${BOT_GIT_BRANCH:-master}"
SERVICE_NAME="${BOT_SERVICE_NAME:-avia-ticket-search-bot.service}"
LOG_PATH="${BOT_UPDATE_LOG_PATH:-$PROJECT_DIR/logs/update.log}"
LOCK_PATH="${BOT_UPDATE_LOCK_PATH:-$PROJECT_DIR/runtime/update.lock}"
STATUS_PATH="${BOT_UPDATE_STATUS_PATH:-$PROJECT_DIR/runtime/update_status.json}"
RESTART_ENABLED="${BOT_RESTART_ENABLED:-true}"
SERVICE_RESTART_WITH_SUDO="${BOT_SERVICE_RESTART_WITH_SUDO:-true}"

DATABASE_PATH="${DATABASE_PATH:-${DATABASE_URL:-$PROJECT_DIR/avia_bot.sqlite3}}"
DATABASE_PATH="${DATABASE_PATH#sqlite:///}"
DATABASE_PATH="${DATABASE_PATH#sqlite://}"
if [[ "$DATABASE_PATH" != /* ]]; then
  DATABASE_PATH="$PROJECT_DIR/$DATABASE_PATH"
fi

mkdir -p "$(dirname "$LOG_PATH")" "$(dirname "$LOCK_PATH")" "$(dirname "$STATUS_PATH")"
touch "$LOG_PATH"
exec >>"$LOG_PATH" 2>&1

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

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
path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
PY
}

cleanup() {
  rm -rf "$LOCK_PATH"
}

on_error() {
  local exit_code=$?
  log "❌ Обновление завершилось ошибкой. Код: $exit_code"
  write_status "error" "Ошибка обновления, код $exit_code"
  exit "$exit_code"
}
trap cleanup EXIT
trap on_error ERR

run() {
  log "▶ $*"
  "$@"
  log "✅ $* — OK"
}

require_command() {
  local missing=0
  for command_name in "$@"; do
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

ensure_project_dir() {
  if [[ ! -d "$PROJECT_DIR" ]]; then
    log "❌ Каталог проекта не найден: $PROJECT_DIR"
    write_status "error" "Каталог проекта не найден"
    exit 1
  fi
  cd "$PROJECT_DIR"
  if [[ ! -d ".git" ]]; then
    log "❌ Каталог не является Git-репозиторием: $PROJECT_DIR"
    write_status "error" "Каталог не является Git-репозиторием"
    exit 1
  fi
}

ensure_git_safe_directory() {
  local output
  if output="$(git status --short 2>&1 >/dev/null)"; then
    return 0
  fi

  if grep -qi "detected dubious ownership" <<<"$output"; then
    log "⚠️ Git сообщил о dubious ownership для $PROJECT_DIR"
    log "▶ Добавляю safe.directory только для текущего каталога проекта"
    run git config --global --add safe.directory "$PROJECT_DIR"
    return 0
  fi

  log "$output"
  return 1
}

git_remote_branch_exists() {
  git ls-remote --exit-code --heads origin "$1" >/dev/null 2>&1
}

resolve_branch() {
  if git_remote_branch_exists "$BRANCH"; then
    return 0
  fi

  local current_branch
  current_branch="$(git rev-parse --abbrev-ref HEAD)"
  if [[ "$current_branch" != "HEAD" ]] && git_remote_branch_exists "$current_branch"; then
    log "⚠️ Ветка origin/$BRANCH не найдена. Использую текущую ветку: $current_branch"
    BRANCH="$current_branch"
    return 0
  fi

  local origin_head
  origin_head="$(git remote show origin 2>/dev/null | awk -F': ' '/HEAD branch/ {print $2; exit}')"
  if [[ -n "$origin_head" ]] && git_remote_branch_exists "$origin_head"; then
    log "⚠️ Ветка origin/$BRANCH не найдена. Использую HEAD origin: $origin_head"
    BRANCH="$origin_head"
    return 0
  fi

  log "❌ Не найдена удаленная ветка origin/$BRANCH"
  return 1
}

apply_sqlite_migrations() {
  local migrations_dir="$PROJECT_DIR/migrations"

  if [[ ! -d "$migrations_dir" ]]; then
    log "ℹ️ Каталог migrations отсутствует, SQL-миграции пропущены"
    return 0
  fi

  log "▶ Применение SQL-миграций из $migrations_dir"
  log "🗄 Путь к базе данных: $DATABASE_PATH"
  run python3 "$PROJECT_DIR/scripts/run_migrations.py" --database "$DATABASE_PATH" --migrations-dir "$migrations_dir"
  log "✅ SQL-миграции обработаны"
}
systemctl_cmd() {
  if [[ "$SERVICE_RESTART_WITH_SUDO" == "true" ]] && [[ "$EUID" -ne 0 ]]; then
    sudo systemctl "$@"
  else
    systemctl "$@"
  fi
}

restart_service() {
  if [[ "$RESTART_ENABLED" != "true" ]]; then
    log "ℹ️ Перезапуск сервиса отключен: BOT_RESTART_ENABLED=$RESTART_ENABLED"
    return 0
  fi

  if ! command -v systemctl >/dev/null 2>&1; then
    log "❌ systemctl не найден. Невозможно перезапустить сервис."
    return 1
  fi

  if [[ "$SERVICE_RESTART_WITH_SUDO" == "true" ]] && [[ "$EUID" -ne 0 ]] && ! command -v sudo >/dev/null 2>&1; then
    log "❌ sudo не найден, но BOT_SERVICE_RESTART_WITH_SUDO=true"
    return 1
  fi

  local load_state
  load_state="$(systemctl show "$SERVICE_NAME" --property=LoadState --value 2>/dev/null || true)"
  if [[ -z "$load_state" || "$load_state" == "not-found" ]]; then
    log "❌ systemd-сервис $SERVICE_NAME не найден. Проверьте BOT_SERVICE_NAME."
    return 1
  fi

  log "ℹ️ Найден systemd-сервис: $SERVICE_NAME"
  run systemctl_cmd restart "$SERVICE_NAME"
  run systemctl_cmd is-active "$SERVICE_NAME"
  log "✅ Сервис $SERVICE_NAME успешно перезапущен"
}

if ! mkdir "$LOCK_PATH" 2>/dev/null; then
  log "⚠️ Обновление уже выполняется: lock $LOCK_PATH существует"
  write_status "error" "Обновление уже выполняется"
  exit 1
fi

log "============================================================"
log "🚀 Обновление AviaTicketSearchBot запущено"
log "Проект: $PROJECT_DIR"
log "Запрошенная ветка: $BRANCH"
log "Сервис: $SERVICE_NAME"
log "Лог обновления: $LOG_PATH"
log "Lock-файл: $LOCK_PATH"
log "Файл статуса: $STATUS_PATH"

require_command git python3
ensure_project_dir
ensure_git_safe_directory
resolve_branch

BEFORE_COMMIT="$(git rev-parse --short HEAD)"
log "Текущий commit до обновления: $BEFORE_COMMIT"
log "Итоговая ветка обновления: $BRANCH"

run git fetch --prune origin "$BRANCH"

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
