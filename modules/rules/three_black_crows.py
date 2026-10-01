from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class ThreeBlackCrows(Rule):
    """Trois corbeaux noirs : trois bougies rouges a clotures decroissantes, chacune ouvrant dans le corps
    de la precedente, meches basses d'au plus R/10 (TA-Lib ShadowVeryShort). Vote -1.

    R : volatilite des 10 dernieres barres, motif compris. Intensite : baisse totale sur 3R.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "ThreeBlackCrows"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        a, b, c = view.bars[-3:]
        r = view.volatility(self.REF)
        if (
            all(bar.body < 0 and bar.lower_shadow <= r / 10 for bar in (a, b, c))
            and a.close <= b.open <= a.open
            and b.close <= c.open <= b.open
            and a.close > b.close > c.close
        ):
            return Vote(-1, min(Decimal(1), (a.open - c.close) / (3 * r)))
        return None
