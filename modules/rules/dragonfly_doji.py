from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class DragonflyDoji(Rule):
    """Doji libellule : doji, meche haute d'au plus R/10, meche basse plus longue. Rejet des bas : +1.

    R : volatilite des 10 dernieres barres, motif compris. Intensite : meche basse sur R.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "DragonflyDoji"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        bar = view.bars[-1]
        r = view.volatility(self.REF)
        if abs(bar.body) <= r / 10 and bar.upper_shadow <= r / 10 and bar.lower_shadow > r / 10:
            return Vote(1, min(Decimal(1), bar.lower_shadow / r))
        return None
