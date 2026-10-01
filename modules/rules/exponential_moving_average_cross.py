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


class ExponentialMovingAverageCross(Rule):
    """Moyenne mobile exponentielle courte contre longue : +1 si la courte est au-dessus, -1 si elle est en dessous.

    Les deux moyennes portent sur une fenetre fixe de 3 x slow barres, amorcees par une moyenne simple,
    comme Macd : le vote ne depend pas de la taille de la vue.
    Intensite : ecart entre les deux moyennes en unites de volatilite, plafonne a 1.
    """

    def __init__(self, weight: Decimal, fast: int, slow: int):
        self.name = f"ExponentialMovingAverageCross({fast},{slow})"
        self.weight = weight
        self.warmup = 3 * slow
        self.fast = fast
        self.slow = slow

    def vote(self, view: View) -> Vote | None:
        closes = [bar.close for bar in view.bars[-self.warmup:]]
        gap = _ema(closes, self.fast)[-1] - _ema(closes, self.slow)[-1]
        if gap == 0:
            return Vote(0, Decimal(0))
        r = view.volatility(self.slow)
        if r == 0:
            return None
        return Vote(1 if gap > 0 else -1, min(Decimal(1), abs(gap) / r))
