from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class ThreeWhiteSoldiers(Rule):
    """Trois soldats blancs : trois bougies vertes a clotures croissantes, chacune ouvrant dans le corps
    de la precedente, meches hautes d'au plus R/10 (TA-Lib ShadowVeryShort). Vote +1.

    R : volatilite des 10 dernieres barres, motif compris. Intensite : progression totale sur 3R.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "ThreeWhiteSoldiers"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        a, b, c = view.bars[-3:]
        r = view.volatility(self.REF)
        if (
            all(bar.body > 0 and bar.upper_shadow <= r / 10 for bar in (a, b, c))
            and a.open <= b.open <= a.close
            and b.open <= c.open <= b.close
            and a.close < b.close < c.close
        ):
            return Vote(1, min(Decimal(1), (c.close - a.open) / (3 * r)))
        return None
