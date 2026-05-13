"""FSM handlers for step-by-step and natural-language flight search."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from api import build_aviasales_search_link, get_popular_directions
import db
from config import settings
from keyboards import (
    after_departure_date_keyboard,
    format_search_confirmation,
    location_choice_keyboard,
    nearby_dates_keyboard,
    offer_subscribe_keyboard,
    passengers_keyboard,
    popular_directions_keyboard,
    search_confirmation_keyboard,
    trip_type_keyboard,
)
from services.autocomplete import autocomplete_locations
from services.calendar_keyboard import build_calendar_keyboard, can_select_date
from services.i18n import defaults_for_language, t, user_language
from services.locations import Location, get_location_by_code
from services.natural_search_parser import parse_natural_search
from services.search_models import FlightSearchRequest
from services.tickets import search_ticket_offers
from states import PopularDirectionState, TicketSearchState
from utils.formatters import format_offer, format_passengers, format_round_trip_no_results

router = Router(name="search")
OFFER_CACHE: dict[str, dict[str, Any]] = {}
CALENDAR_CONTEXT_CACHE: dict[str, dict[str, Any]] = {}


def _cache_offer(user_id: int, offer: dict[str, Any], passengers: int) -> str:
    token = uuid4().hex[:16]
    OFFER_CACHE[token] = {"user_id": user_id, "offer": offer, "passengers": passengers}
    return token


def get_cached_offer(token: str, user_id: int) -> dict[str, Any] | None:
    cached = OFFER_CACHE.get(token)
    if not cached or cached.get("user_id") != user_id:
        return None
    return cached


def _cache_calendar_context(user_id: int, request: FlightSearchRequest) -> str:
    token = uuid4().hex[:16]
    CALENDAR_CONTEXT_CACHE[token] = {"user_id": user_id, **request.as_dict()}
    return token


def _get_calendar_context(token: str, user_id: int) -> dict[str, Any] | None:
    cached = CALENDAR_CONTEXT_CACHE.get(token)
    if not cached or cached.get("user_id") != user_id:
        return None
    return cached


def _profile_defaults(profile: dict[str, Any] | None, language: str) -> tuple[str, str]:
    default_currency, default_market = defaults_for_language(language)
    if not profile:
        return default_currency, default_market
    return str(profile.get("currency_code") or default_currency).upper(), str(profile.get("market_code") or default_market).lower()


def _location_display(location: Location | dict[str, Any] | None, fallback: str) -> str:
    if isinstance(location, Location):
        return location.display_name
    if isinstance(location, dict):
        city = location.get("city") or fallback
        code = location.get("code") or fallback
        return f"{city} ({code})"
    return fallback


async def _ask_location(message: Message, state: FSMContext, query: str, kind: str) -> Location | None:
    language = await user_language(message.from_user.id if message.from_user else None)
    locations = await autocomplete_locations(query, locale=language)
    if not locations:
        await message.answer(await t(message.from_user.id if message.from_user else None, "search.location_not_found"))
        return None
    if len(locations) == 1:
        return locations[0]
    await state.set_state(TicketSearchState.choosing_origin if kind == "origin" else TicketSearchState.choosing_destination)
    await message.answer(await t(message.from_user.id if message.from_user else None, "search.location_choose"), reply_markup=location_choice_keyboard(kind, locations))
    return None


async def _store_location_and_advance(target: Message | CallbackQuery, state: FSMContext, kind: str, location: Location) -> None:
    message = target.message if isinstance(target, CallbackQuery) else target
    user_id = target.from_user.id if isinstance(target, CallbackQuery) else (target.from_user.id if target.from_user else None)
    if kind == "origin":
        await state.update_data(origin=location.code, origin_location=location.as_dict())
        await state.set_state(TicketSearchState.waiting_destination)
        await message.answer(await t(user_id, "search.destination_prompt"))
        return
    data = await state.get_data()
    if location.code == data.get("origin"):
        await message.answer(await t(user_id, "search.same_route"))
        await state.set_state(TicketSearchState.waiting_destination)
        return
    await state.update_data(destination=location.code, destination_location=location.as_dict())
    await state.set_state(TicketSearchState.waiting_trip_type)
    language = await user_language(user_id)
    await message.answer(await t(user_id, "search.trip_type"), reply_markup=trip_type_keyboard(language))


async def _show_calendar(message: Message, state: FSMContext, mode: str, min_date: date | None = None) -> None:
    language = await user_language(message.chat.id if message.chat else None)
    today = date.today()
    await state.set_state(TicketSearchState.waiting_date if mode == "departure" else TicketSearchState.waiting_return_date)
    await message.answer(
        await t(message.chat.id if message.chat else None, "calendar.departure" if mode == "departure" else "calendar.return"),
        reply_markup=build_calendar_keyboard(year=today.year, month=today.month, mode=mode, language_code=language, min_date=min_date),
    )


def _request_from_state(data: dict[str, Any], profile: dict[str, Any] | None, language: str) -> FlightSearchRequest:
    currency, market = _profile_defaults(profile, language)
    origin_location = data.get("origin_location") or {}
    destination_location = data.get("destination_location") or {}
    return FlightSearchRequest(
        origin_iata=data["origin"],
        destination_iata=data["destination"],
        origin_display_name=_location_display(origin_location, data["origin"]),
        destination_display_name=_location_display(destination_location, data["destination"]),
        departure_date=data["departure_date"],
        return_date=data.get("return_date"),
        trip_type=data.get("trip_type") or ("round_trip" if data.get("return_date") else "one_way"),
        adults=int(data.get("adults", 1)),
        children=int(data.get("children", 0)),
        infants=int(data.get("infants", 0)),
        language_code=language,
        currency_code=currency,
        market_code=market,
    )


async def _confirm_request(target: Message | CallbackQuery, state: FSMContext) -> None:
    message = target.message if isinstance(target, CallbackQuery) else target
    user_id = target.from_user.id if isinstance(target, CallbackQuery) else (target.from_user.id if target.from_user else None)
    language = await user_language(user_id)
    request = _request_from_state(await state.get_data(), await db.get_user_profile(user_id) if user_id else None, language)
    await state.update_data(search_request=request.as_dict())
    await state.set_state(TicketSearchState.confirming_search)
    await message.answer(format_search_confirmation(request, language), reply_markup=search_confirmation_keyboard(language))


async def _send_offers(message: Message, request: FlightSearchRequest) -> None:
    user_id = message.from_user.id if message.from_user else None
    if request.trip_type == "round_trip" and request.return_date:
        await message.answer(
            f"🔎 Ищу билеты {request.origin_iata} → {request.destination_iata} → {request.origin_iata}:\n"
            f"вылет {request.departure_date}, возвращение {request.return_date}.\n"
            f"Пассажиры: {format_passengers(total=request.api_passengers)}. Валюта: {request.currency_code}."
        )
    else:
        await message.answer(await t(user_id, "search.loading", origin=request.origin_iata, destination=request.destination_iata, date=request.departure_date, passengers=request.api_passengers, currency=request.currency_code))
    try:
        offers = await search_ticket_offers(
            request.origin_iata,
            request.destination_iata,
            request.departure_date,
            trip_type=request.trip_type,
            return_date=request.return_date,
            currency=request.currency_code,
            market=request.market_code,
        )
    except Exception as error:  # noqa: BLE001
        await db.record_bot_event(user_id, "api_error", f"search {request.origin_iata}->{request.destination_iata}: {error}")
        await message.answer(await t(user_id, "search.api_error"))
        return

    await db.record_search_history(user_id, request.origin_iata, request.destination_iata, request.departure_date, request.api_passengers, len(offers), "success" if offers else "no_results")
    if not offers:
        if request.trip_type == "round_trip":
            link = build_aviasales_search_link(
                request.origin_iata,
                request.destination_iata,
                request.departure_date,
                trip_type=request.trip_type,
                return_date=request.return_date,
                passengers=request.api_passengers,
                marker=settings.marker,
                market=request.market_code,
            )
            await message.answer(
                format_round_trip_no_results(request.origin_iata, request.destination_iata, request.departure_date, request.return_date, link),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        else:
            await message.answer(await t(user_id, "search.no_results"))
        return
    await message.answer(await t(user_id, "search.source_notice"))
    for index, offer in enumerate(offers[: settings.ticket_results_limit], start=1):
        display_offer = dict(offer)
        display_offer["currency"] = request.currency_code
        if request.trip_type == "round_trip":
            display_offer["link"] = build_aviasales_search_link(request.origin_iata, request.destination_iata, request.departure_date, trip_type=request.trip_type, return_date=request.return_date, passengers=request.api_passengers, marker=settings.marker, market=request.market_code)
        token = _cache_offer(user_id or 0, display_offer, request.api_passengers)
        await message.answer(format_offer(display_offer, index, request.api_passengers, trip_type=request.trip_type, departure_date=request.departure_date, return_date=request.return_date), parse_mode="HTML", disable_web_page_preview=True, reply_markup=offer_subscribe_keyboard(token))
    token = _cache_calendar_context(user_id or 0, request)
    await message.answer(await t(user_id, "nearby.prompt"), reply_markup=nearby_dates_keyboard(token, request.language_code))


@router.message(Command("search"))
async def search_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(TicketSearchState.waiting_origin)
    await message.answer(await t(message.from_user.id if message.from_user else None, "search.origin_prompt"))


@router.message(TicketSearchState.waiting_origin)
async def process_origin(message: Message, state: FSMContext) -> None:
    location = await _ask_location(message, state, message.text or "", "origin")
    if location:
        await _store_location_and_advance(message, state, "origin", location)


@router.callback_query(TicketSearchState.choosing_origin, F.data.startswith("loc:origin:"))
async def choose_origin(callback: CallbackQuery, state: FSMContext) -> None:
    location = get_location_by_code((callback.data or "").split(":")[-1])
    if location:
        await _store_location_and_advance(callback, state, "origin", location)
    await callback.answer()


@router.message(TicketSearchState.waiting_destination)
async def process_destination(message: Message, state: FSMContext) -> None:
    location = await _ask_location(message, state, message.text or "", "destination")
    if location:
        await _store_location_and_advance(message, state, "destination", location)


@router.callback_query(TicketSearchState.choosing_destination, F.data.startswith("loc:destination:"))
async def choose_destination(callback: CallbackQuery, state: FSMContext) -> None:
    location = get_location_by_code((callback.data or "").split(":")[-1])
    if location:
        await _store_location_and_advance(callback, state, "destination", location)
    await callback.answer()


@router.callback_query(TicketSearchState.waiting_trip_type, F.data.startswith("trip_type:"))
async def choose_trip_type(callback: CallbackQuery, state: FSMContext) -> None:
    trip_type = (callback.data or "").split(":")[-1]
    await state.update_data(trip_type=trip_type)
    await _show_calendar(callback.message, state, "departure")
    await callback.answer()


@router.callback_query(F.data.startswith("cal:month:"))
async def change_calendar_month(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, mode, year, month = (callback.data or "").split(":")
    language = await user_language(callback.from_user.id)
    data = await state.get_data()
    min_date = datetime.fromisoformat(data["departure_date"]).date() if mode == "return" and data.get("departure_date") else None
    await callback.message.edit_reply_markup(reply_markup=build_calendar_keyboard(year=int(year), month=int(month), mode=mode, language_code=language, min_date=min_date))
    await callback.answer()


@router.callback_query(F.data == "cal:past")
async def calendar_past(callback: CallbackQuery) -> None:
    await callback.answer(await t(callback.from_user.id, "calendar.past"), show_alert=True)


@router.callback_query(F.data.startswith("cal:select:"))
async def select_calendar_date(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, mode, raw_date = (callback.data or "").split(":")
    selected = datetime.fromisoformat(raw_date).date()
    data = await state.get_data()
    min_date = datetime.fromisoformat(data["departure_date"]).date() if mode == "return" and data.get("departure_date") else None
    if not can_select_date(selected, min_date=min_date):
        await callback.answer(await t(callback.from_user.id, "calendar.after_departure" if min_date else "calendar.past"), show_alert=True)
        return
    if mode == "departure":
        await state.update_data(departure_date=raw_date)
        await state.set_state(TicketSearchState.waiting_after_departure_choice)
        await callback.message.answer(await t(callback.from_user.id, "calendar.departure") + f" {raw_date}", reply_markup=after_departure_date_keyboard(await user_language(callback.from_user.id)))
    else:
        await state.update_data(return_date=raw_date, trip_type="round_trip")
        await _show_passengers(callback.message, state, callback.from_user.id)
    await callback.answer()


@router.callback_query(TicketSearchState.waiting_after_departure_choice, F.data.startswith("date_flow:"))
async def after_departure_choice(callback: CallbackQuery, state: FSMContext) -> None:
    choice = (callback.data or "").split(":")[-1]
    if choice == "return":
        data = await state.get_data()
        min_date = datetime.fromisoformat(data["departure_date"]).date()
        await _show_calendar(callback.message, state, "return", min_date=min_date)
    else:
        await state.update_data(trip_type="one_way", return_date=None)
        await _show_passengers(callback.message, state, callback.from_user.id)
    await callback.answer()


async def _show_passengers(message: Message, state: FSMContext, user_id: int | None) -> None:
    data = await state.get_data()
    adults, children, infants = int(data.get("adults", 1)), int(data.get("children", 0)), int(data.get("infants", 0))
    await state.update_data(adults=adults, children=children, infants=infants)
    await state.set_state(TicketSearchState.waiting_passengers)
    language = await user_language(user_id)
    await message.answer(await t(user_id, "passengers.title", adults=adults, children=children, infants=infants), reply_markup=passengers_keyboard(adults, children, infants, language))


@router.callback_query(TicketSearchState.waiting_passengers, F.data.startswith("pax:"))
async def choose_passengers(callback: CallbackQuery, state: FSMContext) -> None:
    parts = (callback.data or "").split(":")
    if parts[1] == "confirm":
        await _confirm_request(callback, state)
        await callback.answer()
        return
    if parts[1] == "noop":
        await callback.answer()
        return
    field, action = parts[1], parts[2]
    data = await state.get_data()
    value = int(data.get(field, 1 if field == "adults" else 0)) + (1 if action == "+" else -1)
    if field == "adults":
        value = max(1, value)
    else:
        value = max(0, value)
    await state.update_data(**{field: value})
    data = await state.get_data()
    await callback.message.edit_text(await t(callback.from_user.id, "passengers.title", adults=data.get("adults", 1), children=data.get("children", 0), infants=data.get("infants", 0)), reply_markup=passengers_keyboard(data.get("adults", 1), data.get("children", 0), data.get("infants", 0), await user_language(callback.from_user.id)))
    await callback.answer()


@router.callback_query(TicketSearchState.confirming_search, F.data == "confirm:search")
async def confirm_search(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    request_data = data.get("search_request") or _request_from_state(data, await db.get_user_profile(callback.from_user.id), await user_language(callback.from_user.id)).as_dict()
    request = FlightSearchRequest(**request_data)
    await state.clear()
    await _send_offers(callback.message, request)
    await callback.answer()


@router.callback_query(TicketSearchState.confirming_search, F.data.startswith("confirm:edit_"))
async def edit_confirmed(callback: CallbackQuery, state: FSMContext) -> None:
    action = (callback.data or "").split(":")[-1]
    if action == "edit_route":
        await state.set_state(TicketSearchState.waiting_origin)
        await callback.message.answer(await t(callback.from_user.id, "search.origin_prompt"))
    elif action == "edit_dates":
        await _show_calendar(callback.message, state, "departure")
    else:
        await _show_passengers(callback.message, state, callback.from_user.id)
    await callback.answer()


@router.message(PopularDirectionState.waiting_origin)
async def process_popular_origin(message: Message, state: FSMContext) -> None:
    location = await _ask_location(message, state, message.text or "", "popular_origin")
    if not location:
        return
    directions = await get_popular_directions(location.code, limit=5)
    await state.clear()
    if not directions:
        await message.answer("Популярные направления не найдены.")
        return
    await message.answer("Популярные направления:", reply_markup=popular_directions_keyboard(location.code, directions))


@router.message(F.text)
async def natural_search_message(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        return
    user_id = message.from_user.id if message.from_user else None
    language = await user_language(user_id)
    parsed = parse_natural_search(message.text or "", language_code=language)
    if parsed.confidence < 0.4:
        return
    data: dict[str, Any] = {"adults": parsed.passengers.adults, "children": parsed.passengers.children, "infants": parsed.passengers.infants, "trip_type": parsed.trip_type}
    if parsed.origin_text:
        origins = await autocomplete_locations(parsed.origin_text, locale=language, limit=2)
        if origins:
            data.update(origin=origins[0].code, origin_location=origins[0].as_dict())
    if parsed.destination_text:
        destinations = await autocomplete_locations(parsed.destination_text, locale=language, limit=2)
        if destinations:
            data.update(destination=destinations[0].code, destination_location=destinations[0].as_dict())
    if parsed.departure_date:
        data["departure_date"] = parsed.departure_date
    if parsed.return_date:
        data["return_date"] = parsed.return_date
    await state.update_data(**data)
    if not data.get("origin"):
        await state.set_state(TicketSearchState.waiting_origin)
        await message.answer(await t(user_id, "natural.missing_origin"))
        return
    if not data.get("destination"):
        await state.set_state(TicketSearchState.waiting_destination)
        await message.answer(await t(user_id, "natural.missing_destination"))
        return
    if not data.get("departure_date"):
        await _show_calendar(message, state, "departure")
        return
    await _confirm_request(message, state)


@router.callback_query(F.data.startswith("calendar:skip:"))
async def skip_nearby_calendar(callback: CallbackQuery) -> None:
    await callback.message.edit_text("OK")
    await callback.answer()
