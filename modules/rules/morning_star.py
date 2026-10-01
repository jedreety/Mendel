from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class MorningStar(Rule):
    """Etoile du matin, variante sans gap (la crypto ouvre a la cloture precedente). Vote +1.

    Longue bougie rouge (corps d'au moins R/2), petit corps (sous R/2), puis bougie verte qui clot
    au-dela de 30 % du corps de la premiere (penetration par defaut de TA-Lib).
    R : volatilite des 10 dernieres barres, motif compris. Intensite : corps de la verte sur R.
    """

    REF = 10
    PENETRATION = Decimal("0.3")

    def __init__(self, weight: Decimal):
        self.name = "MorningStar"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        first, star, last = view.bars[-3:]
        r = view.volatility(self.REF)
        if (
            first.body < 0
            and abs(first.body) >= r / 2
            and abs(star.body) < r / 2
            and last.body > 0
            and last.close > first.close + self.PENETRATION * abs(first.body)
        ):
            return Vote(1, min(Decimal(1), last.body / r))
        return None
