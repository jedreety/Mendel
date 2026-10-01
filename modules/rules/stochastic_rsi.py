from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class StochasticRsi(Rule):
    """RSI stochastique de Chande et Kroll : position du dernier RSI de Cutler (`rsi_period` variations) dans
    l'amplitude des `period` derniers RSI, lue en retour a la moyenne : sous `lower` +1, au-dessus de `upper` -1,
    entre les deux s'abstient. Un RSI indefini (aucune variation) ou des RSI tous egaux : s'abstient.

    Intensite : profondeur au-dela du seuil, rapportee a la marge jusqu'a 0 ou 100.
    """

    def __init__(self, weight: Decimal, rsi_period: int, period: int, lower: Decimal, upper: Decimal):
        self.name = f"StochasticRsi({rsi_period},{period},{lower},{upper})"
        self.weight = weight
        self.warmup = rsi_period + period
        self.rsi_period = rsi_period
        self.period = period
        self.lower = lower
        self.upper = upper

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.warmup:]
        changes = [bar.close - prev.close for prev, bar in zip(bars, bars[1:])]
        values = []
        for end in range(self.rsi_period, len(changes) + 1):
            window = changes[end - self.rsi_period:end]
            gains = sum((change for change in window if change > 0), Decimal(0))
            losses = sum((-change for change in window if change < 0), Decimal(0))
            if gains + losses == 0:
                return None
            values.append(100 * gains / (gains + losses))
        high, low = max(values), min(values)
        if high == low:
            return None
        k = 100 * (values[-1] - low) / (high - low)
        if k < self.lower:
            return Vote(1, (self.lower - k) / self.lower)
        if k > self.upper:
            return Vote(-1, (k - self.upper) / (100 - self.upper))
        return None
