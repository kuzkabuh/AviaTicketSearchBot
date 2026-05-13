#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${REPO_URL:-https://github.com/kuzkabuh/AviaTicketSearchBot.git}"
PROJECT_DIR="${BOT_PROJECT_DIR:-/opt/Bots/AviaTicketSearchBot}"
SERVICE_NAME="${BOT_SERVICE_NAME:-avia-ticket-search-bot.service}"
SERVICE_USER="${BOT_SERVICE_USER:-avia-bot}"
BRANCH="${BOT_GIT_BRANCH:-master}"

echo "🚀 Установка AviaTicketSearchBot..."

if [[ "$EUID" -ne 0 ]]; then
  echo "❌ Этот скрипт нужно запускать с sudo или от root."
  exit 1
fi

echo "📦 Устанавливаем системные зависимости..."
apt-get update
apt-get install -y git python3 python3-pip python3-venv sqlite3

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  echo "👤 Создаём пользователя сервиса: $SERVICE_USER"
  useradd --system --home-dir "$PROJECT_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

if systemctl is-active --quiet "$SERVICE_NAME"; then
  echo "🔄 Останавливаем текущую службу..."
  systemctl stop "$SERVICE_NAME"
fi

echo "📁 Готовим каталог проекта: $PROJECT_DIR"
mkdir -p "$(dirname "$PROJECT_DIR")"

if [[ -d "$PROJECT_DIR/.git" ]]; then
  echo "📥 Репозиторий уже существует, обновляем рабочую копию..."
  git -C "$PROJECT_DIR" fetch origin "$BRANCH"
  git -C "$PROJECT_DIR" checkout "$BRANCH"
  git -C "$PROJECT_DIR" pull --ff-only origin "$BRANCH"
else
  rm -rf "$PROJECT_DIR"
  if ! git clone --branch "$BRANCH" "$REPO_URL" "$PROJECT_DIR"; then
    echo "⚠️ Ветка $BRANCH не найдена при клонировании, клонируем ветку по умолчанию origin."
    git clone "$REPO_URL" "$PROJECT_DIR"
  fi
fi

cd "$PROJECT_DIR"
chmod +x update.sh

echo "🔋 Создаём виртуальное окружение..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "📦 Устанавливаем Python-зависимости..."
pip install --upgrade pip
pip install -r requirements.txt

if [[ ! -f ".env" && -f ".env.example" ]]; then
  echo "⚙️ Создан .env из .env.example"
  cp .env.example .env
  sed -i "s|^BOT_PROJECT_DIR=.*|BOT_PROJECT_DIR=$PROJECT_DIR|" .env
  sed -i "s|^BOT_SERVICE_NAME=.*|BOT_SERVICE_NAME=$SERVICE_NAME|" .env
  sed -i "s|^BOT_UPDATE_SCRIPT=.*|BOT_UPDATE_SCRIPT=$PROJECT_DIR/update.sh|" .env
  sed -i "s|^BOT_UPDATE_LOG_PATH=.*|BOT_UPDATE_LOG_PATH=$PROJECT_DIR/logs/update.log|" .env
  sed -i "s|^BOT_UPDATE_LOCK_PATH=.*|BOT_UPDATE_LOCK_PATH=$PROJECT_DIR/runtime/update.lock|" .env
  sed -i "s|^BOT_UPDATE_STATUS_PATH=.*|BOT_UPDATE_STATUS_PATH=$PROJECT_DIR/runtime/update_status.json|" .env
  sed -i "s|^BOT_RUNTIME_DIR=.*|BOT_RUNTIME_DIR=$PROJECT_DIR/runtime|" .env
  echo "✅ Отредактируйте его: sudo nano $PROJECT_DIR/.env"
fi

mkdir -p logs runtime
chown -R "$SERVICE_USER":"$SERVICE_USER" "$PROJECT_DIR"

echo "🔧 Настраиваем systemd службу: $SERVICE_NAME"
cat > "/etc/systemd/system/$SERVICE_NAME" <<EOF
[Unit]
Description=AviaTicketSearchBot - Telegram bot for flight ticket search
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=-$PROJECT_DIR/.env
Environment="PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PROJECT_DIR/.venv/bin/python $PROJECT_DIR/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=avia-ticket-search-bot

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo "✅ Установка завершена!"
echo ""
echo "📌 Что дальше:"
echo "1. Заполните .env:        sudo nano $PROJECT_DIR/.env"
echo "2. Запустите сервис:      sudo systemctl restart $SERVICE_NAME"
echo "3. Проверьте статус:      sudo systemctl status $SERVICE_NAME"
echo "4. Логи systemd:          journalctl -u $SERVICE_NAME -f"
echo "5. Лог обновлений:        tail -n 100 $PROJECT_DIR/logs/update.log"
