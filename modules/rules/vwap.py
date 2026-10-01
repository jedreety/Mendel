from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Vwap(Rule):
    """Cloture contre le VWAP glissant sur `period` barres (prix typique pondere par le volume) :
    au-dessus +1, en dessous -1, s'abstient sans volume.

    Intensite : ecart en unites de volatilite, plafonne a 1.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"Vwap({period})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period:]
        volume = sum((bar.volume for bar in bars), Decimal(0))
        if volume == 0:
            return None
        vwap = sum(((bar.high + bar.low + bar.close) / 3 * bar.volume for bar in bars), Decimal(0)) / volume
        gap = bars[-1].close - vwap
        if gap == 0:
            return Vote(0, Decimal(0))
        r = view.volatility(self.period)
        if r == 0:
            return None
        return Vote(1 if gap > 0 else -1, min(Decimal(1), abs(gap) / r))
