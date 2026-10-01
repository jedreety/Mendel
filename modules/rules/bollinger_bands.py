from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class BollingerBands(Rule):
    """Bandes de Bollinger lues en retour a la moyenne : cloture sous la bande basse +1,
    au-dessus de la bande haute -1, entre les deux s'abstient.

    Bandes : moyenne des clotures sur `period` barres, plus ou moins `width` ecarts-types (population).
    Pour la lecture en cassure, envelopper dans Inverted.
    Intensite : depassement au-dela de la bande en ecarts-types, rapporte a width, plafonne a 1.
    """

    def __init__(self, weight: Decimal, period: int, width: Decimal):
        self.name = f"BollingerBands({period},{width})"
        self.weight = weight
        self.warmup = period
        self.period = period
        self.width = width

    def vote(self, view: View) -> Vote | None:
        closes = [bar.close for bar in view.bars[-self.period:]]
        mean = sum(closes, Decimal(0)) / self.period
        deviation = (sum(((close - mean) ** 2 for close in closes), Decimal(0)) / self.period).sqrt()
        if deviation == 0:
            return None
        z = (closes[-1] - mean) / deviation
        if z < -self.width:
            return Vote(1, min(Decimal(1), (-z - self.width) / self.width))
        if z > self.width:
            return Vote(-1, min(Decimal(1), (z - self.width) / self.width))
        return None
