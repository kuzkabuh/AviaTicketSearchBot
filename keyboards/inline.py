"""Inline-клавиатуры, построенные через InlineKeyboardBuilder aiogram 3.x."""

from typing import Any

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.i18n import SUPPORTED_CURRENCIES, translate
from services.locations import Location
from services.search_models import FlightSearchRequest
from utils.formatters import format_passengers


def popular_directions_keyboard(origin: str, directions: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    """Создает кнопки популярных направлений."""
    builder = InlineKeyboardBuilder()
    for direction in directions:
        destination = direction.get("destination")
        if not destination:
            continue
        price = direction.get("price") or "—"
        airline = direction.get("airline") or "—"
        currency = direction.get("currency") or "RUB"
        builder.button(text=f"{destination} · от {price} {currency} · {airline}", callback_data=f"popular:{origin}:{destination}")
    builder.adjust(1)
    return builder.as_markup()


def location_choice_keyboard(kind: str, locations: list[Location]) -> InlineKeyboardMarkup:
    """Кнопки выбора города/аэропорта при неоднозначном названии."""
    builder = InlineKeyboardBuilder()
    for location in locations:
        builder.button(text=location.display_name, callback_data=f"loc:{kind}:{location.code}")
    builder.adjust(1)
    return builder.as_markup()


def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=translate("ru", "language.ru"), callback_data="settings:language:set:ru")
    builder.button(text=translate("en", "language.en"), callback_data="settings:language:set:en")
    builder.adjust(1)
    return builder.as_markup()


def settings_keyboard(language_code: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=translate(language_code, "settings.language"), callback_data="settings:language")
    builder.button(text=translate(language_code, "settings.currency"), callback_data="settings:currency")
    builder.button(text=translate(language_code, "settings.back"), callback_data="settings:back")
    builder.adjust(1)
    return builder.as_markup()


def currency_keyboard(language_code: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for currency in sorted(SUPPORTED_CURRENCIES):
        builder.button(text=currency, callback_data=f"settings:currency:set:{currency}")
    builder.button(text=translate(language_code, "settings.back"), callback_data="menu:settings")
    builder.adjust(3, 1)
    return builder.as_markup()


def trip_type_keyboard(language_code: str = "ru") -> InlineKeyboardMarkup:
    """Кнопки выбора типа поездки."""
    builder = InlineKeyboardBuilder()
    builder.button(text=translate(language_code, "trip.one_way"), callback_data="trip_type:one_way")
    builder.button(text=translate(language_code, "trip.round_trip"), callback_data="trip_type:round_trip")
    builder.adjust(1)
    return builder.as_markup()


def after_departure_date_keyboard(language_code: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=translate(language_code, "calendar.one_way"), callback_data="date_flow:one_way")
    builder.button(text=translate(language_code, "calendar.choose_return"), callback_data="date_flow:return")
    builder.adjust(1)
    return builder.as_markup()


def passengers_keyboard(adults: int, children: int, infants: int, language_code: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"− {translate(language_code, 'passengers.adults')}", callback_data="pax:adults:-")
    builder.button(text=str(adults), callback_data="pax:noop")
    builder.button(text=f"+ {translate(language_code, 'passengers.adults')}", callback_data="pax:adults:+")
    builder.button(text=f"− {translate(language_code, 'passengers.children')}", callback_data="pax:children:-")
    builder.button(text=str(children), callback_data="pax:noop")
    builder.button(text=f"+ {translate(language_code, 'passengers.children')}", callback_data="pax:children:+")
    builder.button(text=f"− {translate(language_code, 'passengers.infants')}", callback_data="pax:infants:-")
    builder.button(text=str(infants), callback_data="pax:noop")
    builder.button(text=f"+ {translate(language_code, 'passengers.infants')}", callback_data="pax:infants:+")
    builder.button(text=translate(language_code, "passengers.confirm"), callback_data="pax:confirm")
    builder.adjust(3, 3, 3, 1)
    return builder.as_markup()


def search_confirmation_keyboard(language_code: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=translate(language_code, "confirm.search"), callback_data="confirm:search")
    builder.button(text=translate(language_code, "confirm.edit_route"), callback_data="confirm:edit_route")
    builder.button(text=translate(language_code, "confirm.edit_dates"), callback_data="confirm:edit_dates")
    builder.button(text=translate(language_code, "confirm.edit_passengers"), callback_data="confirm:edit_passengers")
    builder.adjust(1)
    return builder.as_markup()


def nearby_dates_keyboard(token: str, language_code: str = "ru") -> InlineKeyboardMarkup:
    """Кнопки для просмотра или пропуска календарных цен рядом с датой поиска."""
    builder = InlineKeyboardBuilder()
    builder.button(text=translate(language_code, "nearby.show"), callback_data=f"calendar:nearby:{token}")
    builder.button(text=translate(language_code, "nearby.skip"), callback_data=f"calendar:skip:{token}")
    builder.adjust(1)
    return builder.as_markup()


def offer_subscribe_keyboard(token: str) -> InlineKeyboardMarkup:
    """Кнопка подписки на конкретный найденный вариант."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Отслеживать цену", callback_data=f"sub:create:{token}")
    return builder.as_markup()


def notification_mode_keyboard(token: str) -> InlineKeyboardMarkup:
    """Кнопки выбора режима уведомлений для подписки."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 При любом изменении", callback_data=f"sub:mode:any_change:{token}")
    builder.button(text="📉 Только при снижении", callback_data=f"sub:mode:price_drop:{token}")
    builder.button(text="🎯 Ниже заданной суммы", callback_data=f"sub:mode:target_price:{token}")
    builder.adjust(1)
    return builder.as_markup()


def subscriptions_keyboard(subscriptions: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    """Кнопки управления активными подписками пользователя."""
    builder = InlineKeyboardBuilder()
    for subscription in subscriptions:
        subscription_id = subscription["id"]
        route = f"{subscription.get('origin_code')}→{subscription.get('destination_code')}"
        builder.button(text=f"🔄 Проверить цену сейчас · {route}", callback_data=f"sub:check:{subscription_id}")
        builder.button(text=f"❌ Удалить · {route}", callback_data=f"sub:delete:{subscription_id}")
    builder.adjust(1)
    return builder.as_markup()


def start_search_keyboard(is_admin: bool = False, language_code: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура быстрого перехода к основным сценариям бота."""
    builder = InlineKeyboardBuilder()
    builder.button(text=translate(language_code, "menu.search"), callback_data="menu:search")
    builder.button(text=translate(language_code, "menu.smart_search"), callback_data="menu:smart_search")
    builder.button(text=translate(language_code, "menu.popular"), callback_data="menu:popular")
    builder.button(text=translate(language_code, "menu.subscriptions"), callback_data="menu:subscriptions")
    builder.button(text=translate(language_code, "menu.news"), callback_data="menu:news")
    builder.button(text=translate(language_code, "menu.settings"), callback_data="menu:settings")
    if is_admin:
        builder.button(text=translate(language_code, "menu.admin"), callback_data="menu:admin")
    builder.adjust(1)
    return builder.as_markup()


def format_search_confirmation(request: FlightSearchRequest, language_code: str = "ru") -> str:
    lines = [
        translate(language_code, "confirm.title"),
        translate(language_code, "confirm.route", origin=request.origin_display_name, destination=request.destination_display_name),
        translate(language_code, "confirm.departure", date=request.departure_date),
    ]
    if request.return_date:
        lines.append(translate(language_code, "confirm.return", date=request.return_date))
    lines.append(f"Пассажиры: {format_passengers(request.adults, request.children, request.infants)}")
    lines.append(translate(language_code, "confirm.currency", currency=request.currency_code))
    return "\n".join(lines)


def news_menu_keyboard(language_code: str = "ru") -> InlineKeyboardMarkup:
    """User news menu."""
    builder = InlineKeyboardBuilder()
    builder.button(text=translate(language_code, "news.menu.russian_airlines"), callback_data="news:list:russian")
    builder.button(text=translate(language_code, "news.menu.sales"), callback_data="news:list:discount_sale")
    builder.button(text=translate(language_code, "news.menu.promo_codes"), callback_data="news:list:promo_code")
    builder.button(text=translate(language_code, "news.menu.new_routes"), callback_data="news:list:new_route")
    builder.button(text=translate(language_code, "news.menu.resumed_routes"), callback_data="news:list:route_resumed")
    builder.button(text=translate(language_code, "news.menu.for_you"), callback_data="news:for_you")
    builder.button(text=translate(language_code, "news.menu.subscriptions"), callback_data="news:subscriptions")
    builder.adjust(1)
    return builder.as_markup()

def news_card_keyboard(news: dict[str, Any], language_code: str = "ru") -> InlineKeyboardMarkup:
    """Buttons below a news card."""
    builder = InlineKeyboardBuilder()
    if news.get("related_destination_iata"):
        builder.button(text=translate(language_code, "news.cards.search_flights"), callback_data=f"news:search:{news['id']}")
    elif news.get("category") in {"discount_sale", "promo_code"}:
        builder.button(text=translate(language_code, "news.cards.check_flights"), callback_data="menu:search")
    builder.button(text=translate(language_code, "news.cards.source"), url=str(news.get("source_url") or "https://www.aviasales.ru"))
    builder.adjust(1)
    return builder.as_markup()

def news_subscriptions_keyboard(language_code: str = "ru") -> InlineKeyboardMarkup:
    """Basic news subscription choices."""
    builder = InlineKeyboardBuilder()
    builder.button(text=translate(language_code, "news.subscriptions.all"), callback_data="news:sub:all")
    builder.button(text=translate(language_code, "news.subscriptions.all_russian"), callback_data="news:sub:all_russian_airlines")
    builder.button(text=translate(language_code, "news.subscriptions.personalized"), callback_data="news:sub:personalized")
    for category in ("discount_sale", "promo_code", "new_route", "route_resumed", "seasonal_schedule"):
        builder.button(text=translate(language_code, f"news.categories.{category}"), callback_data=f"news:subcat:{category}")
    builder.adjust(1)
    return builder.as_markup()
