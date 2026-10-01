from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class KeltnerChannel(Rule):
    """Canal de Keltner lu en retour a la moyenne : cloture sous la bande basse +1, au-dessus de la bande
    haute -1, entre les deux s'abstient.

    Centre : moyenne simple du prix typique sur `period` barres, comme chez Keltner (1960). Bandes : plus ou
    moins `width` unites de volatilite. Pour la lecture en cassure, envelopper dans Inverted.
    Intensite : depassement au-dela de la bande, rapporte a la demi-largeur du canal, plafonne a 1.
    """

    def __init__(self, weight: Decimal, period: int, width: Decimal):
        self.name = f"KeltnerChannel({period},{width})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period
        self.width = width

    def vote(self, view: View) -> Vote | None:
        typical = [(bar.high + bar.low + bar.close) / 3 for bar in view.bars[-self.period:]]
        center = sum(typical, Decimal(0)) / self.period
        band = self.width * view.volatility(self.period)
        if band == 0:
            return None
        close = view.bars[-1].close
        if close < center - band:
            return Vote(1, min(Decimal(1), (center - band - close) / band))
        if close > center + band:
            return Vote(-1, min(Decimal(1), (close - center - band) / band))
        return None
