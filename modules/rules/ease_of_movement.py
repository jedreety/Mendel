from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class EaseOfMovement(Rule):
    """Ease of Movement d'Arms sur `period` barres, variante sans moyenne mobile : somme des deplacements du
    milieu de barre, multiplies par l'amplitude et divises par le volume. Une hausse large sur faible volume
    pese lourd : le prix monte sans effort. Vote le signe, 0 a l'equilibre, s'abstient sans volume.

    Une barre sans volume ne compte pas.
    Intensite : somme signee rapportee a la somme des valeurs absolues, entre 0 et 1.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"EaseOfMovement({period})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period - 1:]
        values = [
            (bar.high + bar.low - prev.high - prev.low) / 2 * bar.range / bar.volume
            for prev, bar in zip(bars, bars[1:])
            if bar.volume > 0
        ]
        if not values:
            return None
        total = sum(values, Decimal(0))
        if total == 0:
            return Vote(0, Decimal(0))
        return Vote(1 if total > 0 else -1, abs(total) / sum((abs(value) for value in values), Decimal(0)))
