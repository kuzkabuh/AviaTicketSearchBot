#!/bin/bash

echo "🚀 Установка AviaTicketSearchBot..."

# === Настройки ===
REPO_URL="https://github.com/kuzkabuh/AviaTicketSearchBot.git"
PROJECT_DIR="/opt/Bots/AviaTicketSearchBot"
SERVICE_NAME="avia-ticket-search-bot"

# === Проверка прав ===
if [ "$EUID" -ne 0 ]; then
  echo "❌ Этот скрипт нужно запускать с sudo или от root."
  exit 1
fi

# === Установка зависимостей ===
echo "📦 Устанавливаем git, если ещё не установлен..."
apt-get update && apt-get install -y git python3 python3-pip

# === Остановка старого сервиса ===
if systemctl is-active --quiet "$SERVICE_NAME"; then
  echo "🔄 Останавливаем текущую службу..."
  systemctl stop "$SERVICE_NAME"
fi

# === Создание директории ===
echo "📁 Создаём директорию проекта: $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# === Клонирование репозитория ===
echo "📥 Клонируем репозиторий с GitHub..."
rm -rf .git  # очищаем, если уже был клонирован
git clone "$REPO_URL" temp_repo
mv temp_repo/* temp_repo/.* . 2>/dev/null || true
rmdir temp_repo

# === Виртуальное окружение ===
echo "🔋 Создаём виртуальное окружение..."
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate

# === Установка зависимостей ===
echo "📦 Устанавливаем зависимости..."
pip install --upgrade pip
pip install -r requirements.txt

# === .env файл ===
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  echo "⚙️ Создан .env из .env.example"
  cp .env.example .env
  echo "✅ Отредактируйте его: nano .env"
fi

# === Логи ===
mkdir -p logs

# === Системная служба ===
echo "🔧 Настраиваем systemd службу..."
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=AviaTicketSearchBot - Telegram-бот для поиска авиабилетов
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
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

# === Перезагрузка systemd ===
echo "🔄 Перезагружаем systemd..."
systemctl daemon-reload

# === Запуск ===
echo "🚀 Включаем и запускаем службу..."
systemctl enable "$SERVICE_NAME" --now

# === Готово ===
echo "✅ Установка завершена!"
echo ""
echo "📌 Что дальше:"
echo "1. Заполните .env:   nano $PROJECT_DIR/.env"
echo "2. Перезапустите:    sudo systemctl restart $SERVICE_NAME"
echo "3. Проверьте статус: sudo systemctl status $SERVICE_NAME"
echo "4. Логи:             journalctl -u $SERVICE_NAME -f"