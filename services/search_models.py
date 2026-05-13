"""Shared flight-search request models used by menu and natural-language flows."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class PassengerCounts:
    """Passenger counters prepared for current and future API capabilities."""

    adults: int = 1
    children: int = 0
    infants: int = 0

    @property
    def total_for_data_api(self) -> int:
        """Return passenger count supported by the current Aviasales Data API integration."""
        return max(1, self.adults + self.children)

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(slots=True)
class FlightSearchRequest:
    """Normalized flight-search request shared by all bot search scenarios."""

    origin_iata: str
    destination_iata: str
    origin_display_name: str
    destination_display_name: str
    departure_date: str
    return_date: str | None = None
    trip_type: str = "one_way"
    adults: int = 1
    children: int = 0
    infants: int = 0
    language_code: str = "ru"
    currency_code: str = "RUB"
    market_code: str = "ru"

    @property
    def passengers(self) -> PassengerCounts:
        return PassengerCounts(self.adults, self.children, self.infants)

    @property
    def api_passengers(self) -> int:
        return self.passengers.total_for_data_api

    def as_dict(self) -> dict[str, object]:
        return asdict(self)
