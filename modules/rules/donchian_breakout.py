from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class DonchianBreakout(Rule):
    """Cassure du canal de Donchian : cloture au-dessus du plus haut des `period` barres precedentes +1,
    sous leur plus bas -1, sinon s'abstient.

    Intensite : depassement en unites de volatilite, plafonne a 1.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"DonchianBreakout({period})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period

    def vote(self, view: View) -> Vote | None:
        previous = view.bars[-self.period - 1:-1]
        close = view.bars[-1].close
        high = max(bar.high for bar in previous)
        low = min(bar.low for bar in previous)
        if close > high:
            return Vote(1, min(Decimal(1), (close - high) / view.volatility(self.period)))
        if close < low:
            return Vote(-1, min(Decimal(1), (low - close) / view.volatility(self.period)))
        return None
