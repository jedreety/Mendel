from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


def _ema(values: list[Decimal], period: int) -> list[Decimal]:
    """Moyenne exponentielle amorcee par la moyenne simple des `period` premieres valeurs."""
    alpha = Decimal(2) / (period + 1)
    current = sum(values[:period], Decimal(0)) / period
    series = [current]
    for value in values[period:]:
        current += alpha * (value - current)
        series.append(current)
    return series


class ExponentialMovingAverage(Rule):
    """Position de la cloture par rapport a sa moyenne mobile exponentielle sur `period` barres.

    La moyenne porte sur une fenetre fixe de 3 x period barres, amorcee par une moyenne simple, comme Macd :
    le vote ne depend pas de la taille de la vue.
    Intensite : ecart en unites de volatilite, plafonne a 1.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"ExponentialMovingAverage({period})"
        self.weight = weight
        self.warmup = 3 * period
        self.period = period

    def vote(self, view: View) -> Vote | None:
        closes = [bar.close for bar in view.bars[-self.warmup:]]
        gap = closes[-1] - _ema(closes, self.period)[-1]
        if gap == 0:
            return Vote(0, Decimal(0))
        r = view.volatility(self.period)
        if r == 0:
            return None
        return Vote(1 if gap > 0 else -1, min(Decimal(1), abs(gap) / r))
