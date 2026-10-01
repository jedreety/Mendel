from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class PiercingLine(Rule):
    """Ligne penetrante, variante sans gap (la crypto ouvre a la cloture precedente). Vote +1.

    Longue bougie rouge (corps d'au moins R/2), puis bougie verte qui ouvre au plus a sa cloture
    et clot au-dessus du milieu de son corps, sans depasser son ouverture.
    R : volatilite des 10 dernieres barres, motif compris. Intensite : corps de la verte sur R.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "PiercingLine"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        prev, bar = view.bars[-2], view.bars[-1]
        r = view.volatility(self.REF)
        middle = (prev.open + prev.close) / 2
        if prev.body < 0 and abs(prev.body) >= r / 2 and bar.body > 0 and bar.open <= prev.close and middle < bar.close < prev.open:
            return Vote(1, min(Decimal(1), bar.body / r))
        return None
