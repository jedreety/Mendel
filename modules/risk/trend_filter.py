from decimal import Decimal

from engine.base import RiskRule
from engine.domain import Portfolio, RiskVerdict, View


class TrendFilter(RiskRule):
    """Refuse l'entree quand la cloture est sous sa moyenne mobile simple sur `period` barres.

    Ne propose aucun sens : il ecarte seulement les achats contre la tendance de fond.
    """

    def __init__(self, period: int):
        self.name = f"TrendFilter({period})"
        self.warmup = period
        self.period = period

    def check(self, view: View, portfolio: Portfolio) -> RiskVerdict:
        closes = [bar.close for bar in view.bars[-self.period:]]
        if closes[-1] < sum(closes, Decimal(0)) / self.period:
            return RiskVerdict(self.name, Decimal(0), "cloture sous la moyenne")
        return RiskVerdict(self.name, Decimal(1), "cloture au-dessus de la moyenne")
