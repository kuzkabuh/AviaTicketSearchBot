"""Экспорт FSM-состояний приложения."""

from states.search_states import PopularDirectionState, TicketSearchState

# Алиасы оставлены для обратной совместимости с ранними вариантами миграции.
SearchStates = TicketSearchState
PopularStates = PopularDirectionState

__all__ = [
    "PopularDirectionState",
    "PopularStates",
    "SearchStates",
    "TicketSearchState",
]
