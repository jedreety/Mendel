from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class SpinningTop(Rule):
    """Toupie : petit corps (entre R/10 et R/2) et deux meches plus longues que lui. Indecision : vote 0.

    Hors toupie, s'abstient. R : volatilite des 10 dernieres barres, motif compris.
    """

    REF = 10

    def __init__(self, weight: Decimal):
        self.name = "SpinningTop"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        bar = view.bars[-1]
        r = view.volatility(self.REF)
        body = abs(bar.body)
        if r / 10 < body < r / 2 and bar.upper_shadow > body and bar.lower_shadow > body:
            return Vote(0, Decimal(0))
        return None
