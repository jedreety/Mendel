from decimal import Decimal

from engine.base import ExitModule
from engine.domain import Position, View, Vote


class TrailingStop(ExitModule):
    """Constat : la cloture recule de `distance` unites de volatilite depuis le plus haut
    atteint depuis l'entree. Evalue a la cloture ; le socle reste le seul stop intrabar.
    """

    def __init__(self, distance: Decimal, period: int):
        self.name = f"TrailingStop({distance},{period})"
        self.warmup = period + 1
        self.distance = distance
        self.period = period

    def vote(self, view: View, position: Position) -> Vote | None:
        if position.peak - view.bars[-1].close >= self.distance * view.volatility(self.period):
            return Vote(1, Decimal(1))
        return None
