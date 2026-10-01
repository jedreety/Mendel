from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class EfficiencyRatio(Rule):
    """Ratio d'efficacite de Kaufman sur `period` barres : deplacement net des clotures rapporte a la somme
    de leurs deplacements. A partir de `threshold`, vote le sens du deplacement net ; en dessous, le marche
    oscille et la regle s'abstient. Sans aucun deplacement, s'abstient.

    Intensite : le ratio, entre 0 et 1.
    """

    def __init__(self, weight: Decimal, period: int, threshold: Decimal):
        self.name = f"EfficiencyRatio({period},{threshold})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period
        self.threshold = threshold

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period - 1:]
        path = sum((abs(bar.close - prev.close) for prev, bar in zip(bars, bars[1:])), Decimal(0))
        if path == 0:
            return None
        change = bars[-1].close - bars[0].close
        ratio = abs(change) / path
        if ratio < self.threshold:
            return None
        if change == 0:
            return Vote(0, Decimal(0))
        return Vote(1 if change > 0 else -1, ratio)
