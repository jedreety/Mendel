from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class ShootingStar(Rule):
    """Etoile filante : forme du marteau inverse, mais apres une hausse. Vote -1.

    Forme : corps sous R/2, meche haute d'au moins deux fois le corps et d'au moins R/2,
    meche basse d'au plus R/10. Hausse : la bougie precedente clot au-dessus de la cloture de 5 barres plus tot.
    R : volatilite des 10 dernieres barres, motif compris. Intensite : meche haute sur R.
    """

    REF = 10
    TREND = 5

    def __init__(self, weight: Decimal):
        self.name = "ShootingStar"
        self.weight = weight
        self.warmup = self.REF + 1

    def vote(self, view: View) -> Vote | None:
        bar = view.bars[-1]
        r = view.volatility(self.REF)
        rise = view.bars[-2].close > view.bars[-2 - self.TREND].close
        shape = (
            abs(bar.body) < r / 2
            and bar.upper_shadow >= 2 * abs(bar.body)
            and bar.upper_shadow >= r / 2
            and bar.lower_shadow <= r / 10
        )
        if rise and shape:
            return Vote(-1, min(Decimal(1), bar.upper_shadow / r))
        return None
