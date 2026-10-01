from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class EveningStar(Rule):
    """Etoile du soir, variante sans gap (la crypto ouvre a la cloture precedente). Vote -1.

    Longue bougie verte (corps d'au moins R/2), petit corps (sous R/2), puis bougie rouge qui clot
    en deca de 30 % du corps de la premiere (penetration par defaut de TA-Lib).
    R : volatilite des 10 dernieres barres, motif compris. Intensite : corps de la rouge sur R.
    """

    REF = 10
    PENETRATION = Decimal("0.3")

    def __init__(self, weight: Decimal):
        self.name = "EveningStar"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        first, star, last = view.bars[-3:]
        r = view.volatility(self.REF)
        if (
            first.body > 0
            and first.body >= r / 2
            and abs(star.body) < r / 2
            and last.body < 0
            and last.close < first.close - self.PENETRATION * first.body
        ):
            return Vote(-1, min(Decimal(1), abs(last.body) / r))
        return None
