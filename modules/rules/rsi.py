from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Rsi(Rule):
    """RSI de Cutler (moyennes simples des hausses et des baisses sur `period` variations), lu en retour
    a la moyenne : sous `lower` +1, au-dessus de `upper` -1, entre les deux s'abstient.

    Intensite : profondeur au-dela du seuil, rapportee a la marge jusqu'a 0 ou 100.
    """

    def __init__(self, weight: Decimal, period: int, lower: Decimal, upper: Decimal):
        self.name = f"Rsi({period},{lower},{upper})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period
        self.lower = lower
        self.upper = upper

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period - 1:]
        changes = [bar.close - prev.close for prev, bar in zip(bars, bars[1:])]
        gains = sum((change for change in changes if change > 0), Decimal(0))
        losses = sum((-change for change in changes if change < 0), Decimal(0))
        if gains + losses == 0:
            return None
        rsi = 100 * gains / (gains + losses)
        if rsi < self.lower:
            return Vote(1, (self.lower - rsi) / self.lower)
        if rsi > self.upper:
            return Vote(-1, (rsi - self.upper) / (100 - self.upper))
        return None
