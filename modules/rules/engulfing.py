from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Engulfing(Rule):
    """Avalement : le corps de la derniere bougie englobe celui de la precedente, de couleur opposee.

    Haussier +1, baissier -1, sinon s'abstient.
    R : volatilite des 10 dernieres barres, motif compris. Intensite : corps de la derniere bougie sur R.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "Engulfing"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        prev, bar = view.bars[-2], view.bars[-1]
        if prev.body < 0 < bar.body and bar.open <= prev.close and bar.close > prev.open:
            direction = 1
        elif prev.body > 0 > bar.body and bar.open >= prev.close and bar.close < prev.open:
            direction = -1
        else:
            return None
        return Vote(direction, min(Decimal(1), abs(bar.body) / view.volatility(self.REF)))
