from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Stochastic(Rule):
    """Stochastique %K sur `period` barres, lu en retour a la moyenne : sous `lower` +1,
    au-dessus de `upper` -1, entre les deux s'abstient. Williams %R en est le miroir exact.

    Intensite : profondeur au-dela du seuil, rapportee a la marge jusqu'a 0 ou 100.
    """

    def __init__(self, weight: Decimal, period: int, lower: Decimal, upper: Decimal):
        self.name = f"Stochastic({period},{lower},{upper})"
        self.weight = weight
        self.warmup = period
        self.period = period
        self.lower = lower
        self.upper = upper

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period:]
        high = max(bar.high for bar in bars)
        low = min(bar.low for bar in bars)
        if high == low:
            return None
        k = 100 * (bars[-1].close - low) / (high - low)
        if k < self.lower:
            return Vote(1, (self.lower - k) / self.lower)
        if k > self.upper:
            return Vote(-1, (k - self.upper) / (100 - self.upper))
        return None
