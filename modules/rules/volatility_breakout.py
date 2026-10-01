from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class VolatilityBreakout(Rule):
    """Cassure de volatilite (Larry Williams) : la bougie clot a plus de `k` fois l'amplitude de la
    precedente au-dessus de son ouverture +1, en dessous -1, sinon s'abstient.

    Intensite : part du corps dans l'amplitude de la bougie.
    """

    def __init__(self, weight: Decimal, k: Decimal):
        self.name = f"VolatilityBreakout({k})"
        self.weight = weight
        self.warmup = 2
        self.k = k

    def vote(self, view: View) -> Vote | None:
        prev, bar = view.bars[-2], view.bars[-1]
        threshold = self.k * prev.range
        if bar.body > threshold:
            return Vote(1, bar.body / bar.range)
        if bar.body < -threshold:
            return Vote(-1, -bar.body / bar.range)
        return None
