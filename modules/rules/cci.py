from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Cci(Rule):
    """Commodity Channel Index de Lambert sur `period` barres, lu en suivi de tendance comme a l'origine :
    au-dessus de +100 +1, sous -100 -1, entre les deux s'abstient.

    Intensite : depassement au-dela de 100, sur 100, plafonne a 1.
    """

    CONSTANT = Decimal("0.015")

    def __init__(self, weight: Decimal, period: int):
        self.name = f"Cci({period})"
        self.weight = weight
        self.warmup = period
        self.period = period

    def vote(self, view: View) -> Vote | None:
        typical = [(bar.high + bar.low + bar.close) / 3 for bar in view.bars[-self.period:]]
        mean = sum(typical, Decimal(0)) / self.period
        deviation = sum((abs(price - mean) for price in typical), Decimal(0)) / self.period
        if deviation == 0:
            return None
        cci = (typical[-1] - mean) / (self.CONSTANT * deviation)
        if cci > 100:
            return Vote(1, min(Decimal(1), (cci - 100) / 100))
        if cci < -100:
            return Vote(-1, min(Decimal(1), (-cci - 100) / 100))
        return None
