from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Marubozu(Rule):
    """Marubozu : corps long (au moins R/2), meches d'au plus R/10 chacune. Vote la couleur.

    R : volatilite des 10 dernieres barres, motif compris. Intensite : corps sur R, plafonne a 1.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "Marubozu"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        bar = view.bars[-1]
        r = view.volatility(self.REF)
        if bar.body != 0 and abs(bar.body) >= r / 2 and bar.upper_shadow <= r / 10 and bar.lower_shadow <= r / 10:
            return Vote(1 if bar.body > 0 else -1, min(Decimal(1), abs(bar.body) / r))
        return None
