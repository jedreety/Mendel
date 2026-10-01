from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class MovingAverage(Rule):
    """Position de la cloture par rapport a sa moyenne mobile simple sur `period` barres.

    Intensite : ecart en unites de volatilite, plafonne a 1.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"MovingAverage({period})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period

    def vote(self, view: View) -> Vote | None:
        closes = [bar.close for bar in view.bars[-self.period:]]
        gap = closes[-1] - sum(closes, Decimal(0)) / self.period
        if gap == 0:
            return Vote(0, Decimal(0))
        return Vote(1 if gap > 0 else -1, min(Decimal(1), abs(gap) / view.volatility(self.period)))
