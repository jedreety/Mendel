from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class InsideBar(Rule):
    """Barre interieure : amplitude contenue dans celle de la precedente. Consolidation : vote 0.

    Hors barre interieure, s'abstient.
    """

    def __init__(self, weight: Decimal):
        self.name = "InsideBar"
        self.weight = weight
        self.warmup = 2

    def vote(self, view: View) -> Vote | None:
        prev, bar = view.bars[-2], view.bars[-1]
        if bar.high <= prev.high and bar.low >= prev.low:
            return Vote(0, Decimal(0))
        return None
