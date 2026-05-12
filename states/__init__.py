"""Экспорт FSM-состояний приложения."""

from states.search_states import PopularDirectionState, TicketSearchState

SearchStates = TicketSearchState
PopularStates = PopularDirectionState

__all__ = [
    "PopularDirectionState",
    "PopularStates",
    "SearchStates",
    "TicketSearchState",
]
