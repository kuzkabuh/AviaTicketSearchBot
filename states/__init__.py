"""Экспорт FSM-состояний приложения."""

from states.search_states import AdminBroadcastState, PopularDirectionState, TicketSearchState

SearchStates = TicketSearchState
PopularStates = PopularDirectionState

__all__ = [
    "AdminBroadcastState",
    "PopularDirectionState",
    "PopularStates",
    "SearchStates",
    "TicketSearchState",
]
