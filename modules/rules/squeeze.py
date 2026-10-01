from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Squeeze(Rule):
    """Sortie de compression, d'apres le TTM Squeeze de Carter : sur l'avant-derniere barre, les bandes de
    Bollinger (`bollinger` ecarts-types) tenaient dans le canal de Keltner (`keltner` unites de volatilite) ;
    sur la derniere, elles en sortent. Vote alors le sens de la cloture par rapport a la moyenne des clotures,
    sinon s'abstient.

    Bandes et canal portent sur `period` barres et partagent la moyenne des clotures pour centre.
    Variante : le momentum de Carter, une regression lineaire, est remplace par l'ecart a cette moyenne.
    Intensite : ecart en unites de volatilite, plafonne a 1.
    """

    def __init__(self, weight: Decimal, period: int, bollinger: Decimal, keltner: Decimal):
        self.name = f"Squeeze({period},{bollinger},{keltner})"
        self.weight = weight
        self.warmup = period + 2
        self.period = period
        self.bollinger = bollinger
        self.keltner = keltner

    def vote(self, view: View) -> Vote | None:
        if self._inside(view) or not self._inside(View(view.symbol, view.bars[:-1])):
            return None
        closes = [bar.close for bar in view.bars[-self.period:]]
        gap = closes[-1] - sum(closes, Decimal(0)) / self.period
        if gap == 0:
            return Vote(0, Decimal(0))
        return Vote(1 if gap > 0 else -1, min(Decimal(1), abs(gap) / view.volatility(self.period)))

    def _inside(self, view: View) -> bool:
        """Les bandes de Bollinger tiennent strictement dans le canal de Keltner sur la derniere barre de `view`."""
        closes = [bar.close for bar in view.bars[-self.period:]]
        mean = sum(closes, Decimal(0)) / self.period
        deviation = (sum(((close - mean) ** 2 for close in closes), Decimal(0)) / self.period).sqrt()
        return self.bollinger * deviation < self.keltner * view.volatility(self.period)
