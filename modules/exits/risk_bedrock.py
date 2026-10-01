from decimal import Decimal

from engine.base import Bedrock, ExitBudget
from engine.domain import Caps, Position, View


class RiskBedrock(Bedrock):
    """Socle de risque par defaut.

    Cap negatif a la distance de stop du budget, cap positif derive par le ratio du budget.
    Le cap negatif est teste en premier : en cas d'ambiguite intrabar, il l'emporte.
    """

    def __init__(self, budget: ExitBudget):
        self.budget = budget
        self.warmup = budget.warmup

    def caps(self, view: View, entry_price: Decimal) -> Caps:
        distance = self.budget.stop_distance(view, entry_price)
        return Caps(entry_price - distance, entry_price + self.budget.target_ratio * distance)

    def check(self, view: View, position: Position) -> str | None:
        bar = view.bars[-1]
        if bar.low <= position.caps.stop:
            return "stop"
        if bar.high >= position.caps.target:
            return "target"
        return None
