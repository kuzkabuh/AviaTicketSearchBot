from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import Message
from aiogram.types import CallbackQuery, Message
from aiogram import Bot
from database import DatabaseManager
from analytics import AnalyticsTracker
from utils import parse_utm_params, extract_referral_id
import asyncio

db_manager = None
analytics_tracker = None

def set_db_manager(manager):
    global db_manager
    db_manager = manager

def set_analytics_tracker(tracker):
    global analytics_tracker
    analytics_tracker = tracker
	
# Глобальные функции для получения городов и рейсов
def get_city_code(city_name: str):
    # Заглушка — в реальном проекте будет обращение к API
    city_codes = {
        "Москва": ("MOW", "Москва"),
        "Казань": ("KZN", "Казань"),
        "СПб": ("LED", "Санкт-Петербург"),
        "Санкт-Петербург": ("LED", "Санкт-Петербург"),
        "Новосибирск": ("OVB", "Новосибирск"),
        "Екатеринбург": ("SVX", "Екатеринбург"),
        "Нижний Новгород": ("GOJ", "Нижний Новгород"),
    }
    return city_codes.get(city_name, (None, None))

async def get_flight_options(origin_code: str, dest_code: str, date: str, passengers: int):
    # Заглушка — в реальном проекте будет вызов API
    return [
        {
            "price": 5600,
            "airline": "S7",
            "departure": "2026-05-27T08:00",
            "arrival": "2026-05-27T10:30",
            "link": "/search?query=..."
        }
    ]

async def send_flight_messages(message: Message, flights, o_code, d_code, o_name, d_name, date, passengers, direction, is_return, return_date):
    # Заглушка — отправка сообщений с результатами
    for flight in flights:
        price = flight.get("price")
        airline = flight.get("airline")
        dep_time = flight.get("departure")
        arr_time = flight.get("arrival")
        link = f"https://www.aviasales.ru{flight.get('link')}"
        
        res_msg = (
            f"{direction}\n"
            f"🛫 {o_name} → {d_name} | {date}\n"
            f"🕐 {dep_time[11:16]} → {arr_time[11:16]}\n"
            f"✈️ {airline}\n"
            f"💰 {price} ₽\n"
            f"🔗 [Купить билет]({link})"
        )
        await message.answer(res_msg, parse_mode="Markdown")

async def start(message: Message, bot: Bot) -> None:
    """Приветствие и обработка реферальных ссылок."""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # Регистрация пользователя
    db_manager.register_user(user_id, username, first_name, last_name)
    
    # Обработка реферальной ссылки
    if message.text and " " in message.text:
        try:
            referrer_id = int(message.text.split()[1])
            if referrer_id != user_id:
                success = db_manager.add_referral(user_id, referrer_id)
                if success:
                    await bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 Пользователь {first_name} перешел по вашей реферальной ссылке!"
                    )
                    # Отслеживание реферального события
                    analytics_tracker.track_event(
                        "referral_joined", 
                        user_id=user_id, 
                        referrer_id=referrer_id
                    )
        except (ValueError, IndexError):
            pass
    
    # Отслеживание события старта
    utm_params = parse_utm_params(message.text if message.text else "")
    analytics_tracker.track_event(
        "start_command", 
        user_id=user_id, 
        utm_source=utm_params.get('utm_source'),
        utm_medium=utm_params.get('utm_medium'),
        utm_campaign=utm_params.get('utm_campaign')
    )
    
    await message.answer(
        "✈️ **Бот-поисковик авиабилетов v5.0 (коммерческая версия)**\n\n"
        "🔍 Ищите билеты и получайте уведомления при снижении цены!\n\n"
        "📌 Команда:\n"
        "`/track Откуда Куда Дата_Туда [Дата_Обратно] Пассажиры`\n\n"
        "✅ Пример: `/track Москва Казань 2026-05-27 2026-05-29 2`\n\n"
        "👥 Пригласи друзей и получи бонусы!\n"
        f"📎 Ваша реферальная ссылка: https://t.me/avia_search_bot?start={user_id}",
        parse_mode="Markdown"
    )

async def track(message: Message, bot: Bot) -> None:
    """Основная логика поиска."""
    # Отслеживание события поиска
    analytics_tracker.track_event("track_command", user_id=message.from_user.id)
    
    args = message.text.split()[1:] if message.text else []
    if len(args) < 3:
        await message.answer(
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
            await message.answer("❌ Кол-во пассажиров: от 1 до 9.")
            return

    except Exception:
        await message.answer("❌ Ошибка в датах или числе пассажиров.")
        return

    o_code, o_name = await get_city_code(raw_origin)
    d_code, d_name = await get_city_code(raw_dest)

    if not o_code or not d_code:
        await message.answer("❌ Город не найден. Попробуйте другое название.")
        return

    # Поиск туда
    await message.answer(f"🔍 Ищу рейсы: {o_name} → {d_name}...")
    flights_to = await get_flight_options(o_code, d_code, dep_date, passengers)
    await send_flight_messages(
        message, flights_to, o_code, d_code, o_name, d_name,
        dep_date, passengers, "ТУДА 🛫", is_return=False, return_date=ret_date
    )

    # Обратно
    if ret_date:
        await asyncio.sleep(1)
        await message.answer(f"🔍 Ищу обратные рейсы: {d_name} → {o_name}...")
        flights_back = await get_flight_options(d_code, o_code, ret_date, passengers)
        await send_flight_messages(
            message, flights_back, d_code, o_code, d_name, o_name,
            ret_date, passengers, "ОБРАТНО 🛬", is_return=True, return_date=ret_date
        )

async def list_subscriptions(message: Message, bot: Bot) -> None:
    """Список подписок."""
    # Отслеживание события просмотра подписок
    analytics_tracker.track_event("list_subscriptions", user_id=message.from_user.id)
    
    subs = db_manager.get_user_subscriptions(message.chat.id)

    if not subs:
        await message.answer("📭 У вас нет активных подписок.")
        return

    for s in subs:
        sid, oname, dname, dep, ret, price = s
        dates = f"📅 {dep}" + (f" → {ret}" if ret else "")
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Удалить", callback_data=f"del|{sid}")]])
        await message.answer(
            f"📍 {oname} → {d_name}\n{dates}\n💰 Порог: {price} ₽",
            reply_markup=btn
        )

async def help_command(message: Message, bot: Bot) -> None:
    """Обработка команды /help."""
    analytics_tracker.track_event("help_command", user_id=message.from_user.id)
    
    await message.answer(
        "ℹ️ **Помощь по боту**\n\n"
        "✈️ Бот помогает находить дешевые авиабилеты и отслеживать их цены.\n\n"
        "📌 Основные команды:\n"
        "• `/track Откуда Куда Дата_Туда [Дата_Обратно] Пассажиры` - поиск и отслеживание\n"
        "• `/list` - просмотр активных подписок\n"
        "• `/help` - помощь\n"
        "• `/support` - поддержка\n\n"
        "👥 **Реферальная программа**\n"
        "Пригласи друзей по ссылке и получи бонусы!\n"
        "Каждый приглашенный друг приносит вам бонусы.\n\n"
        "📈 **Аналитика**\n"
        "Мы отслеживаем количество поисков и покупок для улучшения сервиса.",
        parse_mode="Markdown"
    )

async def support(message: Message, bot: Bot) -> None:
    """Обработка команды /support."""
    analytics_tracker.track_event("support_command", user_id=message.from_user.id)
    
    await message.answer(
        "📞 **Служба поддержки**\n\n"
        "Если у вас возникли вопросы или проблемы с ботом, напишите нам: @aviabot_support\n\n"
        "Мы ответим в течение 24 часов.\n\n"
        "💡 Вы также можете задать вопрос в нашем канале: @aviabot_channel",
        parse_mode="Markdown"
    )