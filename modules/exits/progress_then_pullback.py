from decimal import Decimal

from engine.base import ExitModule
from engine.domain import Position, View, Vote


class ProgressThenPullback(ExitModule):
    """Constat : le prix a fait au moins `advances` nouveaux plus hauts depuis l'entree,
    puis la cloture a recule d'au moins `pullback` (fraction, 0.01 pour 1 %) depuis le plus haut.
    """

    def __init__(self, advances: int, pullback: Decimal):
        self.name = f"ProgressThenPullback({advances},{pullback})"
        self.warmup = 1
        self.advances = advances
        self.pullback = pullback

    def vote(self, view: View, position: Position) -> Vote | None:
        if position.advances >= self.advances and position.peak - view.bars[-1].close >= self.pullback * position.peak:
            return Vote(1, Decimal(1))
        return None
