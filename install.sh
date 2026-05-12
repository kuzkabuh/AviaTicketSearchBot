#!/bin/bash
set -e

echo "🚀 Установка AviaTicketSearchBot..."

# Клонирование репозитория (ветка master)
git clone -b master https://gitverse.ru/kuzkabuh/AviaTicketSearchBot.git .

# Создание виртуального окружения
python3 -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install --upgrade pip
pip install -r requirements.txt

# Создание .env
cp .env.example .env

# Создание папки для логов
mkdir -p logs

echo "✅ Установка завершена!"
echo "📌 Отредактируйте .env: nano .env"
echo "📌 Запуск: source .venv/bin/activate && python main.py"