from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Harami(Rule):
    """Harami : longue bougie (corps d'au moins R/2), puis petit corps (sous R/2) de couleur opposee
    contenu dans le sien. Vote le sens de la seconde, sinon s'abstient.

    R : volatilite des 10 dernieres barres, motif compris. Intensite : corps de la premiere sur R.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "Harami"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        prev, bar = view.bars[-2], view.bars[-1]
        r = view.volatility(self.REF)
        inside = (
            min(bar.open, bar.close) >= min(prev.open, prev.close)
            and max(bar.open, bar.close) <= max(prev.open, prev.close)
        )
        if not (inside and abs(prev.body) >= r / 2 and abs(bar.body) < r / 2):
            return None
        if prev.body < 0 < bar.body:
            return Vote(1, min(Decimal(1), abs(prev.body) / r))
        if prev.body > 0 > bar.body:
            return Vote(-1, min(Decimal(1), abs(prev.body) / r))
        return None
