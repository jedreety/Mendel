from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class CandleColor(Rule):
    """Couleur d'une bougie close : verte +1, rouge -1, sans corps 0.

    offset : 1 pour la derniere bougie close, 2 pour celle d'avant, etc.
    Intensite : part du corps dans l'amplitude de la bougie.
    """

    def __init__(self, weight: Decimal, offset: int):
        self.name = f"CandleColor({offset})"
        self.weight = weight
        self.warmup = offset
        self.offset = offset

    def vote(self, view: View) -> Vote | None:
        bar = view.bars[-self.offset]
        if bar.body == 0:
            return Vote(0, Decimal(0))
        return Vote(1 if bar.body > 0 else -1, abs(bar.body) / bar.range)
