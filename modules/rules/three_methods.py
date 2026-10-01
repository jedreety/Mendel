from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class ThreeMethods(Rule):
    """Trois methodes montantes ou descendantes : longue bougie, trois petits corps contenus dans son
    amplitude, puis longue bougie de meme couleur qui clot au-dela de la premiere. Vote la couleur.

    Long : corps d'au moins R/2. Petit : corps sous R/2. Sinon s'abstient.
    R : volatilite des 10 dernieres barres, motif compris. Intensite : corps de la derniere sur R.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "ThreeMethods"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        first, *middle, last = view.bars[-5:]
        r = view.volatility(self.REF)
        if not (
            abs(first.body) >= r / 2
            and abs(last.body) >= r / 2
            and all(bar.high <= first.high and bar.low >= first.low and abs(bar.body) < r / 2 for bar in middle)
        ):
            return None
        if first.body > 0 and last.body > 0 and last.close > first.close:
            return Vote(1, min(Decimal(1), last.body / r))
        if first.body < 0 and last.body < 0 and last.close < first.close:
            return Vote(-1, min(Decimal(1), abs(last.body) / r))
        return None
