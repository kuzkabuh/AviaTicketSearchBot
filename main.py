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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и обработка реферальных ссылок."""
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    
    # Регистрация пользователя
    register_user(user_id, username, first_name, last_name, context)
    
    # Обработка реферальной ссылки
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user_id:
                success = add_referral(user_id, referrer_id)
                if success:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 Пользователь {first_name} перешел по вашей реферальной ссылке!"
                    )
        except (ValueError, IndexError):
            pass
    
    await update.message.reply_text(
        "✈️ **Бот-поисковик авиабилетов v5.0 (коммерческая версия)**\n\n"
        "🔍 Ищите билеты и получайте уведомления при снижении цены!\n\n"
        "📌 Команда:\n"
        "`/track Откуда Куда Дата_Туда [Дата_Обратно] Пассажиры`\n\n"
        "✅ Пример: `/track Москва Казань 2026-05-27 2026-05-29 2`\n\n"
        "👥 Пригласи друзей и получи бонусы!\n"
        f"📎 Ваша реферальная ссылка: https://t.me/avia_search_bot?start={user_id}",
        parse_mode="Markdown"
    )

async def track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основная логика поиска."""
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "❌ Неверный формат.\nИспользуйте:\n`/track Москва Казань 2026-05-27 [2026-05-29] 2`",
            parse_mode="Markdown"
        )
        return

    try:
        raw_origin, raw_dest, dep_date = args[0], args[1], args[2]
        ret_date = None
        passengers = 1

        if len(args) == 4:
            if "-" in args[3]:
                ret_date = args[3]
            else:
                passengers = int(args[3])
        elif len(args) >= 5:
            ret_date = args[3]
            passengers = int(args[4])

        if not (1 <= passengers <= 9):
            await update.message.reply_text("❌ Кол-во пассажиров: от 1 до 9.")
            return

    except Exception:
        await update.message.reply_text("❌ Ошибка в датах или числе пассажиров.")
        return

    o_code, o_name = await get_city_code(raw_origin)
    d_code, d_name = await get_city_code(raw_dest)

    if not o_code or not d_code:
        await update.message.reply_text("❌ Город не найден. Попробуйте другое название.")
        return

    # Поиск туда
    await update.message.reply_text(f"🔍 Ищу рейсы: {o_name} → {d_name}...")
    flights_to = await get_flight_options(o_code, d_code, dep_date, passengers)
    await send_flight_messages(
        update, flights_to, o_code, d_code, o_name, d_name,
        dep_date, passengers, "ТУДА 🛫", is_return=False, return_date=ret_date
    )

    # Обратно
    if ret_date:
        await asyncio.sleep(1)
        await update.message.reply_text(f"🔍 Ищу обратные рейсы: {d_name} → {o_name}...")
        flights_back = await get_flight_options(d_code, o_code, ret_date, passengers)
        await send_flight_messages(
            update, flights_back, d_code, o_code, d_name, o_name,
            ret_date, passengers, "ОБРАТНО 🛬", is_return=True, return_date=ret_date
        )

async def send_flight_messages(update, flights, o_c, d_c, o_n, d_n, date, psng, label,
                               is_return=False, return_date=None):
    """Отправка сообщений о рейсах."""
    if not flights:
        await update.message.reply_text(f"😔 Рейсы {label.lower()} не найдены.")
        return

    for i, flight in enumerate(flights, 1):
        price = flight['price']
        changes = flight.get('transfers', 0)
        airline = flight.get('airline', '—')
        flight_num = flight.get('flight_number', '')

        callback_data = f"sub|{o_c}|{d_c}|{date}|{return_date or ''}|{psng}|{price}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔔 Отслеживать за {price} ₽", callback_data=callback_data)],
            [InlineKeyboardButton("🔗 Перейти к покупке", url=generate_search_link(o_c, d_c, date, psng, return_date))]
        ])

        msg = (
            f"📍 **Вариант №{i} ({label})**\n"
            f"💰 **Цена: {price} ₽**\n"
            f"📅 {flight['departure_at'][:16].replace('T', ' ')}\n"
            f"🔁 Пересадок: {changes}\n"
            f"✈️ {airline} {flight_num}"
        )
        await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок."""
    query = update.callback_query
    await query.answer()
    data = query.data.split('|')

    if data[0] == "sub":
        _, o_c, d_c, dep, ret, psng, price = data
        _, o_n = await get_city_code(o_c)
        _, d_n = await get_city_code(d_c)
        psng = int(psng)
        price = int(price)

        success = add_subscription(
            query.message.chat.id, o_c, d_c, o_n, d_n, dep, ret if ret != '' else None,
            psng, price
        )

        if success:
            text = f"✅ Подписка активирована!\n📍 {o_n} → {d_n}\n📅 {dep}"
            if ret: text += f" | ← {ret}"
            text += f"\n🔔 Уведомлю при цене < {price} ₽"
        else:
            text = "ℹ️ Вы уже отслеживаете этот маршрут."

        await query.edit_message_text(text=text)

    elif data[0] == "del":
        delete_subscription(data[1])
        await query.edit_message_text(text="🗑 Подписка удалена.")

async def list_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список подписок."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, origin_name, dest_name, departure_date, return_date, last_price 
        FROM subscriptions WHERE user_id = ?
    ''', (update.effective_chat.id,))
    subs = cursor.fetchall()
    conn.close()

    if not subs:
        await update.message.reply_text("📭 У вас нет активных подписок.")
        return

    for s in subs:
        sid, oname, dname, dep, ret, price = s
        dates = f"📅 {dep}" + (f" → {ret}" if ret else "")
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Удалить", callback_data=f"del|{sid}")]])
        await update.message.reply_text(
            f"📍 {oname} → {dname}\n{dates}\n💰 Порог: {price} ₽",
            reply_markup=btn
        )

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
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('track', track))
    app.add_handler(CommandHandler('list', list_subscriptions))
    app.add_handler(CallbackQueryHandler(button_handler))

    if app.job_queue:
        app.job_queue.run_repeating(check_prices_job, interval=14400, first=60)

    logging.info("🚀 Бот v5.0 запущен в коммерческом режиме.")
    app.run_polling()