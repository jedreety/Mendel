from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class MoneyFlowIndex(Rule):
    """MFI sur `period` barres (RSI du prix typique pondere par le volume), lu en retour a la moyenne :
    sous `lower` +1, au-dessus de `upper` -1, entre les deux s'abstient.

    Intensite : profondeur au-dela du seuil, rapportee a la marge jusqu'a 0 ou 100.
    """

    def __init__(self, weight: Decimal, period: int, lower: Decimal, upper: Decimal):
        self.name = f"MoneyFlowIndex({period},{lower},{upper})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period
        self.lower = lower
        self.upper = upper

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period - 1:]
        typical = [(bar.high + bar.low + bar.close) / 3 for bar in bars]
        positive = negative = Decimal(0)
        for i in range(1, len(bars)):
            if typical[i] > typical[i - 1]:
                positive += typical[i] * bars[i].volume
            elif typical[i] < typical[i - 1]:
                negative += typical[i] * bars[i].volume
        if positive + negative == 0:
            return None
        mfi = 100 * positive / (positive + negative)
        if mfi < self.lower:
            return Vote(1, (self.lower - mfi) / self.lower)
        if mfi > self.upper:
            return Vote(-1, (mfi - self.upper) / (100 - self.upper))
        return None
