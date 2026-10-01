from decimal import Decimal

from engine.base import ExitBudget, Sizer
from engine.domain import Portfolio, Tally, View


class FixedRisk(Sizer):
    """Taille telle qu'un stop touche coute `fraction` du capital.

    Quand la volatilite monte, la distance s'elargit et la taille baisse : le budget de risque reste constant.
    """

    def __init__(self, budget: ExitBudget, fraction: Decimal):
        self.budget = budget
        self.fraction = fraction
        self.warmup = budget.warmup

    def size(self, view: View, portfolio: Portfolio, price: Decimal, tally: Tally) -> Decimal:
        return portfolio.cash * self.fraction / self.budget.stop_distance(view, price)
