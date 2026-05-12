import logging
import asyncio
from datetime import datetime
from typing import Optional, Tuple
import sentry_sdk

import aiohttp
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from dotenv import load_dotenv

# Импорты для аналитики и логирования
from logging_config import setup_logging
from analytics import AnalyticsTracker
from database import DatabaseManager
from commands import set_db_manager, set_analytics_tracker, get_handlers as get_command_handlers
from handlers import get_handlers as get_handlers_handlers, set_db_manager as set_db_handlers, set_analytics_tracker as set_analytics_handlers
from utils import parse_utm_params, extract_referral_id, get_command_with_args

load_dotenv()

# --- КОНФИГУРАЦИЯ ---
import os
import sentry_sdk

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN")
MARKER = os.getenv("MARKER", "721904")
SENTRY_DSN = os.getenv("SENTRY_DSN")
DB_NAME = 'flights_bot.db'

# Инициализация Sentry для мониторинга ошибок
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

# Настройка логирования
logger = setup_logging()

# --- БАЗА ДАННЫХ ---
def init_db():
    """Инициализация базы данных."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            origin_code TEXT,
            dest_code TEXT,
            origin_name TEXT,
            dest_name TEXT,
            departure_date TEXT,
            return_date TEXT,
            passengers INTEGER,
            last_price INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, origin_code, dest_code, departure_date, return_date)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            referrer_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_subscription(user_id, o_code, d_code, o_name, d_name, dep, ret, psng, price):
    """Добавление новой подписки (игнорирует дубли)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO subscriptions 
            (user_id, origin_code, dest_code, origin_name, dest_name, departure_date, return_date, passengers, last_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, o_code, d_code, o_name, d_name, dep, ret, psng, price))
        conn.commit()
        return cursor.rowcount > 0  # True если добавлено
    except Exception as e:
        logging.error(f"Ошибка добавления подписки: {e}")
        return False
    finally:
        conn.close()

def delete_subscription(sub_id):
    """Удаление подписки по ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM subscriptions WHERE id = ?', (sub_id,))
    conn.commit()
    conn.close()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def get_city_code(city_name: str) -> Tuple[Optional[str], Optional[str]]:
    """Преобразование названия города в IATA код."""
    url = "https://autocomplete.travelpayouts.com/places2"
    params = {
        "term": city_name,
        "locale": "ru",
        "types[]": "city"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                if data:
                    return data[0]['code'], data[0]['name']
    except Exception as e:
        logging.error(f"Ошибка поиска города: {e}")
    return None, None

def generate_search_link(origin, dest, dep_date, passengers, return_date=None):
    """Генерация прямой ссылки на Aviasales с UTM и marker."""
    dep_formatted = dep_date[8:10] + dep_date[5:7]
    ret_part = f"{return_date[8:10]}{return_date[5:7]}" if return_date else ""
    link = (
        f"https://www.aviasales.ru/search/{origin}{dep_formatted}{dest}{ret_part}{passengers}"
        f"?marker={MARKER}&utm_source=telegram_bot"
    )
    return link

async def get_flight_options(origin, dest, dep_date, passengers) -> list:
    """Получение списка рейсов через API v3/prices_for_dates."""
    url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    params = {
        "origin": origin,
        "destination": dest,
        "departure_at": dep_date,
        "currency": "rub",
        "adults": passengers,
        "token": TRAVELPAYOUTS_TOKEN,
        "limit": 30,
        "one_way": "false",
        "unique": "false",
        "sorting": "price",
        "direct": "false"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                if data.get('success') and data.get('data'):
                    return data['data'][:5]
    except Exception as e:
        logging.error(f"Ошибка API цен: {e}")
    return []

# --- КОМАНДЫ ---
# Удалены дублирующие функции start, track, list_subscriptions, так как они в commands.py
# Удалены button_handler и send_flight_messages, так как они в handlers.py

async def check_prices_job(context: ContextTypes.DEFAULT_TYPE):
    """Фоновая проверка цен."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, origin_code, dest_code, origin_name, dest_name, 
               departure_date, return_date, passengers, last_price 
        FROM subscriptions
    ''')
    subs = cursor.fetchall()
    conn.close()

    for sub in subs:
        sid, uid, o_c, d_c, o_n, d_n, dep, ret, psng, last_p = sub
        try:
            flights = await get_flight_options(o_c, d_c, dep, psng)
            if not flights:
                continue

            current_min_price = flights[0]['price']
            if current_min_price < last_p:
                # Обновляем цену
                conn = sqlite3.connect(DB_NAME)
                conn.cursor().execute(
                    'UPDATE subscriptions SET last_price = ? WHERE id = ?',
                    (current_min_price, sid)
                )
                conn.commit()
                conn.close()

                link = generate_search_link(o_c, d_c, dep, psng, ret)
                btn = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Купить сейчас", url=link)]])
                await context.bot.send_message(
                    chat_id=uid,
                    text=(
                        f"📉 **Цена упала!**\n"
                        f"📍 {o_n} → {d_n}\n"
                        f"📅 {dep}" + (f" → {ret}" if ret else "") + "\n"
                        f"💰 Было: {last_p} ₽ → Стало: {current_min_price} ₽"
                    ),
                    reply_markup=btn,
                    parse_mode="Markdown"
                )
        except Exception as e:
            logging.error(f"Ошибка проверки подписки {sid}: {e}")

if __name__ == '__main__':
    # Инициализация компонентов
    db_manager = DatabaseManager(DB_NAME)
    db_manager.init_db()
    analytics_tracker = AnalyticsTracker(DB_NAME)

    # Передача зависимостей модулям
    set_db_manager(db_manager)
    set_analytics_tracker(analytics_tracker)
    set_db_handlers(db_manager)
    set_analytics_handlers(analytics_tracker)

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Добавление обработчиков из модулей
    for handler in get_command_handlers():
        app.add_handler(handler)
    
    for handler in get_handlers_handlers():
        app.add_handler(handler)
    
    if app.job_queue:
        app.job_queue.run_repeating(check_prices_job, interval=14400, first=60)

    logging.info("🚀 Бот v5.0 запущен в коммерческом режиме.")
    app.run_polling()