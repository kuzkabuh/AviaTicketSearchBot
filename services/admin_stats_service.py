"""Форматирование статистики и аналитики для административной панели."""

from __future__ import annotations

import db

PERIOD_DAYS = {"today": 0, "7d": 7, "30d": 30, "all": None}
PERIOD_TITLES = {"today": "сегодня", "7d": "за 7 дней", "30d": "за 30 дней", "all": "за всё время"}


async def format_overview_statistics() -> str:
    stats = await db.get_overview_stats()
    return (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователи: <b>{stats['users_total']}</b>\n"
        f"🟢 Активны за 24 часа: <b>{stats['users_active_24h']}</b>\n"
        f"📅 Активны за 7 дней: <b>{stats['users_active_7d']}</b>\n"
        f"🗓 Активны за 30 дней: <b>{stats['users_active_30d']}</b>\n\n"
        f"🔍 Поисков билетов всего: <b>{stats['searches_total']}</b>\n"
        f"🔍 Поисков сегодня: <b>{stats['searches_today']}</b>\n"
        f"🔍 Поисков за 7 дней: <b>{stats['searches_7d']}</b>\n\n"
        f"🔔 Подписок всего: <b>{stats['subscriptions_total']}</b>\n"
        f"✅ Активных подписок: <b>{stats['subscriptions_active']}</b>\n"
        f"❌ Отключённых/удалённых: <b>{stats['subscriptions_inactive']}</b>\n\n"
        f"📩 Уведомлений о цене отправлено: <b>{stats['price_notifications']}</b>\n"
        f"🔄 Успешных проверок цен: <b>{stats['price_checks_success']}</b>\n"
        f"⚠️ Ошибок проверки/API: <b>{stats['price_checks_errors']}</b>"
    )


async def format_period_statistics(period: str) -> str:
    days = PERIOD_DAYS.get(period)
    stats = await db.get_period_stats(days)
    return (
        f"📈 <b>Статистика {PERIOD_TITLES.get(period, 'за период')}</b>\n\n"
        f"👤 Новых пользователей: <b>{stats['new_users']}</b>\n"
        f"🔍 Поисков билетов: <b>{stats['searches']}</b>\n"
        f"🔔 Созданных подписок: <b>{stats['subscriptions_created']}</b>\n"
        f"📩 Уведомлений об изменении цены: <b>{stats['notifications']}</b>\n"
        f"⚠️ Ошибок API/фоновой задачи: <b>{stats['errors']}</b>"
    )


async def format_popular_routes(days: int = 30) -> str:
    routes = await db.get_popular_routes(days=days, limit=10)
    origins = await db.get_popular_cities("origin", days=days, limit=5)
    destinations = await db.get_popular_cities("destination", days=days, limit=5)
    if not routes:
        return "✈️ <b>Популярные направления</b>\n\nПока нет данных о поисках."
    route_lines = [f"{idx}. {row['origin_code']} → {row['destination_code']} — {row['count']} поисков" for idx, row in enumerate(routes, 1)]
    origin_lines = ", ".join(f"{row['code']} ({row['count']})" for row in origins) or "нет данных"
    destination_lines = ", ".join(f"{row['code']} ({row['count']})" for row in destinations) or "нет данных"
    return (
        "✈️ <b>Топ направлений за 30 дней</b>\n\n"
        + "\n".join(route_lines)
        + f"\n\n🛫 Популярные вылеты: {origin_lines}\n🛬 Популярные прилёты: {destination_lines}"
    )


async def format_subscription_analytics() -> str:
    stats = await db.get_subscription_analytics()
    return (
        "🔔 <b>Аналитика подписок</b>\n\n"
        f"Всего создано: <b>{stats['total']}</b>\n"
        f"Активно сейчас: <b>{stats['active']}</b>\n"
        f"Удалено/отключено: <b>{stats['inactive']}</b>\n"
        f"Среднее активных на пользователя: <b>{stats['avg_active_per_user']:.2f}</b>\n"
        f"📉 Уведомлений о снижении: <b>{stats['price_down_notifications']}</b>\n"
        f"📈 Уведомлений о росте: <b>{stats['price_up_notifications']}</b>\n"
        f"🚫 Рейс не найден при проверке: <b>{stats['not_found_checks']}</b>"
    )


async def format_users_summary() -> str:
    stats = await db.get_users_summary()
    return (
        "👥 <b>Пользователи</b>\n\n"
        f"Всего пользователей: <b>{stats['total']}</b>\n"
        f"Новых сегодня: <b>{stats['new_today']}</b>\n"
        f"Активных за 7 дней: <b>{stats['active_7d']}</b>\n"
        f"С активными подписками: <b>{stats['with_active_subscriptions']}</b>"
    )


async def format_latest_users(limit: int = 10) -> str:
    users = await db.get_latest_users(limit)
    if not users:
        return "🆕 <b>Последние пользователи</b>\n\nПока нет зарегистрированных пользователей."
    lines = ["🆕 <b>Последние пользователи</b>\n"]
    for idx, user in enumerate(users, 1):
        username = f"@{user['username']}" if user.get("username") else "без username"
        name = " ".join(part for part in (user.get("first_name"), user.get("last_name")) if part) or "без имени"
        lines.append(
            f"{idx}. {name} ({username}) — ID <code>{user['telegram_user_id']}</code>\n"
            f"   Первый запуск: <code>{user['created_at']}</code>\n"
            f"   Последняя активность: <code>{user['last_activity_at']}</code>"
        )
    return "\n".join(lines)


async def format_users_with_subscriptions(limit: int = 10) -> str:
    users = await db.get_users_with_active_subscriptions(limit)
    if not users:
        return "🔔 <b>Пользователи с подписками</b>\n\nАктивных подписок пока нет."
    lines = ["🔔 <b>Пользователи с подписками</b>\n"]
    for idx, user in enumerate(users, 1):
        username = f"@{user['username']}" if user.get("username") else "без username"
        lines.append(f"{idx}. ID <code>{user['telegram_user_id']}</code> ({username}) — {user['active_subscriptions']} активных")
    return "\n".join(lines)
