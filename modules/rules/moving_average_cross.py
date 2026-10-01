from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class MovingAverageCross(Rule):
    """Moyenne mobile simple courte contre longue : +1 si la courte est au-dessus, -1 si elle est en dessous.

    Intensite : ecart entre les deux moyennes en unites de volatilite, plafonne a 1.
    """

    def __init__(self, weight: Decimal, fast: int, slow: int):
        self.name = f"MovingAverageCross({fast},{slow})"
        self.weight = weight
        self.warmup = slow + 1
        self.fast = fast
        self.slow = slow

    def vote(self, view: View) -> Vote | None:
        closes = [bar.close for bar in view.bars[-self.slow:]]
        gap = sum(closes[-self.fast:], Decimal(0)) / self.fast - sum(closes, Decimal(0)) / self.slow
        if gap == 0:
            return Vote(0, Decimal(0))
        return Vote(1 if gap > 0 else -1, min(Decimal(1), abs(gap) / view.volatility(self.slow)))
