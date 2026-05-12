from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from database import DatabaseManager
from analytics import AnalyticsTracker

db_manager = None
analytics_tracker = None

def set_db_manager(manager):
    global db_manager
    db_manager = manager

def set_analytics_tracker(tracker):
    global analytics_tracker
    analytics_tracker = tracker

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

        success = db_manager.add_subscription(
            query.message.chat.id, o_c, d_c, o_n, d_n, dep, ret if ret != '' else None,
            psng, price
        )

        if success:
            text = f"✅ Подписка активирована!\n📍 {o_n} → {d_n}\n📅 {dep}"
            if ret: text += f" | ← {ret}"
            text += f"\n🔔 Уведомлю при цене < {price} ₽"
            # Отслеживание события подписки
            analytics_tracker.track_event("subscription_created", user_id=query.message.chat.id)
        else:
            text = "ℹ️ Вы уже отслеживаете этот маршрут."

        await query.edit_message_text(text=text)

    elif data[0] == "del":
        db_manager.delete_subscription(data[1])
        await query.edit_message_text(text="🗑 Подписка удалена.")
        # Отслеживание события удаления подписки
        analytics_tracker.track_event("subscription_deleted", user_id=query.message.chat.id)

async def purchase_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка переходов по ссылкам покупки."""
    # Отслеживание события покупки (переход по ссылке)
    text = update.message.text if update.message else ""
    utm_params = parse_utm_params(text)
    referrer_id = extract_referral_id(text)
    
    analytics_tracker.track_event(
        "purchase_link_clicked", 
        user_id=update.effective_user.id, 
        utm_source=utm_params.get('utm_source'),
        utm_medium=utm_params.get('utm_medium'),
        utm_campaign=utm_params.get('utm_campaign'),
        referrer_id=referrer_id
    )
    
# Обработчики для регистрации в основном приложении
def get_handlers():
    return [
        CallbackQueryHandler(button_handler),
        MessageHandler(filters.TEXT & filters.Regex(r'https://www.aviasales.ru/search/.*\?marker=\d+'), purchase_handler)
    ]