from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Aroon(Rule):
    """Aroon sur `period` barres : Aroon haut moins Aroon bas. Vote le signe, 0 a egalite.

    A egalite de plus haut ou de plus bas, le plus recent compte.
    Intensite : ecart entre Aroon haut et Aroon bas, sur 100.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"Aroon({period})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period - 1:]
        last = len(bars) - 1
        since_high = last - max(range(len(bars)), key=lambda i: (bars[i].high, i))
        since_low = last - max(range(len(bars)), key=lambda i: (-bars[i].low, i))
        spread = Decimal(since_low - since_high) / self.period
        if spread == 0:
            return Vote(0, Decimal(0))
        return Vote(1 if spread > 0 else -1, abs(spread))
