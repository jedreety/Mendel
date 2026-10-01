from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class NarrowRange(Rule):
    """Cassure apres contraction, d'apres Crabel : l'avant-derniere barre a l'amplitude la plus faible des
    `length` barres qui precedent la derniere. La derniere clot au-dessus de son plus haut +1, sous son plus
    bas -1, sinon s'abstient. Exemple : NR7 pour length = 7.

    Intensite : depassement en unites de volatilite (periode length), plafonne a 1.
    """

    def __init__(self, weight: Decimal, length: int):
        self.name = f"NarrowRange({length})"
        self.weight = weight
        self.warmup = length + 1
        self.length = length

    def vote(self, view: View) -> Vote | None:
        previous = view.bars[-self.length - 1:-1]
        prev, bar = previous[-1], view.bars[-1]
        if prev.range > min(b.range for b in previous):
            return None
        if bar.close > prev.high:
            return Vote(1, min(Decimal(1), (bar.close - prev.high) / view.volatility(self.length)))
        if bar.close < prev.low:
            return Vote(-1, min(Decimal(1), (prev.low - bar.close) / view.volatility(self.length)))
        return None
