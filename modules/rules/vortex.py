from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Vortex(Rule):
    """Indicateur Vortex de Botes et Siepman sur `period` barres : VI+ contre VI-. Vote le cote dominant,
    0 a egalite, s'abstient sans amplitude.

    VM+ : |plus haut - plus bas precedent|. VM- : |plus bas - plus haut precedent|.
    VI : somme des VM sur somme des true ranges.
    Intensite : |VI+ - VI-|, plafonne a 1.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"Vortex({period})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period - 1:]
        plus = sum((abs(bar.high - prev.low) for prev, bar in zip(bars, bars[1:])), Decimal(0))
        minus = sum((abs(bar.low - prev.high) for prev, bar in zip(bars, bars[1:])), Decimal(0))
        ranges = self.period * view.volatility(self.period)
        if ranges == 0:
            return None
        if plus == minus:
            return Vote(0, Decimal(0))
        return Vote(1 if plus > minus else -1, min(Decimal(1), abs(plus - minus) / ranges))
