from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class DarkCloudCover(Rule):
    """Couverture en nuage noir, variante sans gap (la crypto ouvre a la cloture precedente). Vote -1.

    Longue bougie verte (corps d'au moins R/2), puis bougie rouge qui ouvre au moins a sa cloture
    et clot sous le milieu de son corps, sans passer sous son ouverture.
    R : volatilite des 10 dernieres barres, motif compris. Intensite : corps de la rouge sur R.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "DarkCloudCover"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        prev, bar = view.bars[-2], view.bars[-1]
        r = view.volatility(self.REF)
        middle = (prev.open + prev.close) / 2
        if prev.body > 0 and prev.body >= r / 2 and bar.body < 0 and bar.open >= prev.close and prev.open < bar.close < middle:
            return Vote(-1, min(Decimal(1), abs(bar.body) / r))
        return None
