from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Doji(Rule):
    """Doji : corps d'au plus R/10 (TA-Lib BodyDoji). Indecision : vote 0, "ne rien faire".

    Hors doji, s'abstient. R : volatilite des 10 dernieres barres, motif compris.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "Doji"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        if abs(view.bars[-1].body) <= view.volatility(self.REF) / 10:
            return Vote(0, Decimal(0))
        return None
