from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class VolumeSurge(Rule):
    """Pic de volume : volume de la derniere bougie d'au moins `ratio` fois la moyenne des `period`
    precedentes. Vote alors la couleur de la bougie, sinon s'abstient.

    Intensite : part du corps dans l'amplitude de la bougie.
    """

    def __init__(self, weight: Decimal, period: int, ratio: Decimal):
        self.name = f"VolumeSurge({period},{ratio})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period
        self.ratio = ratio

    def vote(self, view: View) -> Vote | None:
        bar = view.bars[-1]
        average = sum((b.volume for b in view.bars[-self.period - 1:-1]), Decimal(0)) / self.period
        if average == 0 or bar.volume < self.ratio * average:
            return None
        if bar.body == 0:
            return Vote(0, Decimal(0))
        return Vote(1 if bar.body > 0 else -1, abs(bar.body) / bar.range)
