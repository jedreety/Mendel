from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class ThreeInside(Rule):
    """Trois a l'interieur : un harami (longue bougie, puis petit corps oppose contenu dans le sien),
    confirme par une troisieme bougie de la couleur du petit corps qui clot au-dela de l'ouverture
    de la premiere. Haussier +1, baissier -1, sinon s'abstient.

    R : volatilite des 10 dernieres barres, motif compris. Intensite : corps de la troisieme sur R.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "ThreeInside"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        a, b, c = view.bars[-3:]
        r = view.volatility(self.REF)
        inside = (
            min(b.open, b.close) >= min(a.open, a.close)
            and max(b.open, b.close) <= max(a.open, a.close)
        )
        if not (inside and abs(a.body) >= r / 2 and abs(b.body) < r / 2):
            return None
        if a.body < 0 < b.body and c.body > 0 and c.close > a.open:
            return Vote(1, min(Decimal(1), c.body / r))
        if a.body > 0 > b.body and c.body < 0 and c.close < a.open:
            return Vote(-1, min(Decimal(1), abs(c.body) / r))
        return None
