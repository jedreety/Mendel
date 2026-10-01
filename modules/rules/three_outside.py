from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class ThreeOutside(Rule):
    """Trois a l'exterieur : un avalement, confirme par une troisieme bougie de meme couleur que
    la deuxieme qui clot au-dela d'elle. Haussier +1, baissier -1, sinon s'abstient.

    R : volatilite des 10 dernieres barres, motif compris. Intensite : corps de la troisieme sur R.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "ThreeOutside"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        a, b, c = view.bars[-3:]
        r = view.volatility(self.REF)
        if a.body < 0 < b.body and b.open <= a.close and b.close > a.open and c.body > 0 and c.close > b.close:
            return Vote(1, min(Decimal(1), c.body / r))
        if a.body > 0 > b.body and b.open >= a.close and b.close < a.open and c.body < 0 and c.close < b.close:
            return Vote(-1, min(Decimal(1), abs(c.body) / r))
        return None
