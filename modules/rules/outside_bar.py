from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class OutsideBar(Rule):
    """Barre exterieure : amplitude qui deborde la precedente des deux cotes. Vote le cote ou elle clot.

    Hors barre exterieure, s'abstient.
    Intensite : ecart entre la cloture et le milieu de la barre, rapporte a la demi-amplitude.
    """

    def __init__(self, weight: Decimal):
        self.name = "OutsideBar"
        self.weight = weight
        self.warmup = 2

    def vote(self, view: View) -> Vote | None:
        prev, bar = view.bars[-2], view.bars[-1]
        if not (bar.high > prev.high and bar.low < prev.low):
            return None
        gap = bar.close - (bar.high + bar.low) / 2
        if gap == 0:
            return Vote(0, Decimal(0))
        return Vote(1 if gap > 0 else -1, abs(gap) / (bar.range / 2))
