from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Autocorrelation(Rule):
    """Autocorrelation d'ordre 1 des variations de cloture sur `period` variations. Positive, le marche
    prolonge ses mouvements : vote le sens de la derniere variation. Negative, il les corrige : vote le
    sens oppose. Nulle, ou derniere variation nulle : 0. Variations toutes egales : s'abstient.

    Intensite : |autocorrelation|, entre 0 et 1.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"Autocorrelation({period})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period - 1:]
        changes = [bar.close - prev.close for prev, bar in zip(bars, bars[1:])]
        mean = sum(changes, Decimal(0)) / self.period
        deviations = [change - mean for change in changes]
        variance = sum((deviation * deviation for deviation in deviations), Decimal(0))
        if variance == 0:
            return None
        rho = sum((a * b for a, b in zip(deviations, deviations[1:])), Decimal(0)) / variance
        if rho == 0 or changes[-1] == 0:
            return Vote(0, Decimal(0))
        last = 1 if changes[-1] > 0 else -1
        return Vote(last if rho > 0 else -last, abs(rho))
