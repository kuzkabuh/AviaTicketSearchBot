#!/bin/bash

echo "🚀 Установка AviaTicketSearchBot в /opt/Bots/AviaTicketSearchBot..."

echo "📁 Создание системной директории..."
sudo mkdir -p /opt/Bots/AviaTicketSearchBot
sudo chown $USER:$USER /opt/Bots/AviaTicketSearchBot

echo "📦 Клонирование репозитория (ветка master)..."
cd /opt/Bots/AviaTicketSearchBot

git clone -b master https://gitverse.ru/kuzkabuh/AviaTicketSearchBot.git temp_repo

# Перемещение файлов в корень
mv temp_repo/* temp_repo/.* . 2>/dev/null || true
rmdir temp_repo

echo "🔋 Создание виртуального окружения..."
python3 -m venv .venv
source .venv/bin/activate

echo "📦 Установка зависимостей..."
pip install --upgrade pip
pip install -r requirements.txt

echo "⚙️ Настройка переменных окружения..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ Файл .env создан. Заполните TELEGRAM_TOKEN и TRAVELPAYOUTS_TOKEN."
fi

echo "📂 Создание папки для логов..."
mkdir -p logs

echo " systemd: создание службы..."
sudo tee /etc/systemd/system/avia-ticket-search-bot.service > /dev/null << EOF
[Unit]
Description=AviaTicketSearchBot - Telegram-бот для поиска авиабилетов
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/Bots/AviaTicketSearchBot
Environment="PATH=/opt/Bots/AviaTicketSearchBot/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/Bots/AviaTicketSearchBot/.venv/bin/python /opt/Bots/AviaTicketSearchBot/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=avia-ticket-search-bot

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Служба создана: /etc/systemd/system/avia-ticket-search-bot.service"

echo "🔄 Перезагрузка systemd..."
sudo systemctl daemon-reload

echo "🚀 Включение и запуск службы..."
sudo systemctl enable avia-ticket-search-bot
sudo systemctl start avia-ticket-search-bot

echo "✅ Установка завершена!"

echo ""
echo "📌 Дальнейшие шаги:"
echo "1. Отредактируйте .env:"
echo "   nano /opt/Bots/AviaTicketSearchBot/.env"
echo "2. Перезапустите бота после настройки:"
echo "   sudo systemctl restart avia-ticket-search-bot"
echo "3. Проверьте статус:"
echo "   sudo systemctl status avia-ticket-search-bot"
echo "4. Просмотр логов:"
echo "   journalctl -u avia-ticket-search-bot -f"

echo ""
echo "💡 Бот будет автоматически перезапускаться при сбоях."
