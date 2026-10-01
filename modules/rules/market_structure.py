from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class MarketStructure(Rule):
    """Structure de marche : `length` barres de suite a plus hauts et plus bas croissants +1,
    decroissants -1, sinon s'abstient.

    Intensite : deplacement des clotures en unites de volatilite ramenees a l'horizon
    par racine de length, plafonne a 1.
    """

    def __init__(self, weight: Decimal, length: int):
        self.name = f"MarketStructure({length})"
        self.weight = weight
        self.warmup = length + 1
        self.length = length

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.length - 1:]
        pairs = list(zip(bars, bars[1:]))
        if all(bar.high > prev.high and bar.low > prev.low for prev, bar in pairs):
            direction = 1
        elif all(bar.high < prev.high and bar.low < prev.low for prev, bar in pairs):
            direction = -1
        else:
            return None
        move = abs(bars[-1].close - bars[0].close)
        scale = view.volatility(self.length) * Decimal(self.length).sqrt()
        return Vote(direction, min(Decimal(1), move / scale))
