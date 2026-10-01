from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Tweezer(Rule):
    """Pinces : deux plus bas egaux (a R/20 pres, TA-Lib Equal), rouge puis verte : +1.
    Deux plus hauts egaux, verte puis rouge : -1. Sinon s'abstient.

    R : volatilite des 10 dernieres barres, motif compris. Intensite : corps de la derniere bougie sur R.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "Tweezer"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        prev, bar = view.bars[-2], view.bars[-1]
        r = view.volatility(self.REF)
        if prev.body < 0 < bar.body and abs(prev.low - bar.low) <= r / 20:
            direction = 1
        elif prev.body > 0 > bar.body and abs(prev.high - bar.high) <= r / 20:
            direction = -1
        else:
            return None
        return Vote(direction, min(Decimal(1), abs(bar.body) / r))
