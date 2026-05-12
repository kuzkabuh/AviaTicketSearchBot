#!/bin/bash

echo "🔄 Обновляем AviaTicketSearchBot..."

cd /opt/Bots/AviaTicketSearchBot || { echo "❌ Не удалось перейти в папку"; exit 1; }

# Стягиваем изменения
git pull origin master

# Обновляем зависимости
source .venv/bin/activate
pip install -r requirements.txt

# Перезапускаем бота
sudo systemctl restart avia-ticket-search-bot

echo "✅ Бот обновлён и перезапущен!"