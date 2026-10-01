from decimal import Decimal

from engine.base import ExitModule
from engine.domain import Position, View, Vote


class LevelCross(ExitModule):
    """Constat : la cloture franchit un niveau absolu declare.

    above : True pour fermer au-dessus du niveau, False pour fermer en dessous.
    Evalue a la cloture, comme les autres constats.
    """

    def __init__(self, level: Decimal, above: bool):
        self.name = f"LevelCross({'>' if above else '<'}{level})"
        self.warmup = 1
        self.level = level
        self.above = above

    def vote(self, view: View, position: Position) -> Vote | None:
        close = view.bars[-1].close
        crossed = close > self.level if self.above else close < self.level
        return Vote(1, Decimal(1)) if crossed else None
