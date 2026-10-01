from decimal import Decimal

from engine.base import ExitBudget, ExitModule
from engine.domain import Position, View, Vote


class TimeExit(ExitModule):
    """Constat : la position est detenue depuis la duree maximale du budget."""

    def __init__(self, budget: ExitBudget):
        self.name = "TimeExit"
        self.warmup = 0
        self.budget = budget

    def vote(self, view: View, position: Position) -> Vote | None:
        if position.bars_held >= self.budget.hold_limit():
            return Vote(1, Decimal(1))
        return None
