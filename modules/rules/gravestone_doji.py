from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class GravestoneDoji(Rule):
    """Doji pierre tombale : doji, meche basse d'au plus R/10, meche haute plus longue. Rejet des hauts : -1.

    R : volatilite des 10 dernieres barres, motif compris. Intensite : meche haute sur R.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "GravestoneDoji"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        bar = view.bars[-1]
        r = view.volatility(self.REF)
        if abs(bar.body) <= r / 10 and bar.lower_shadow <= r / 10 and bar.upper_shadow > r / 10:
            return Vote(-1, min(Decimal(1), bar.upper_shadow / r))
        return None
