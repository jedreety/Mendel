from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class DirectionalMovement(Rule):
    """Mouvement directionnel de Wilder sur `period` barres, sans lissage : +DM contre -DM.

    Vote le cote dominant, 0 a egalite, s'abstient sans aucun mouvement.
    Intensite : DX = |+DM - -DM| / (+DM + -DM), entre 0 et 1.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"DirectionalMovement({period})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period - 1:]
        plus = minus = Decimal(0)
        for prev, bar in zip(bars, bars[1:]):
            up = bar.high - prev.high
            down = prev.low - bar.low
            if up > down and up > 0:
                plus += up
            elif down > up and down > 0:
                minus += down
        if plus + minus == 0:
            return None
        if plus == minus:
            return Vote(0, Decimal(0))
        return Vote(1 if plus > minus else -1, abs(plus - minus) / (plus + minus))
