from decimal import Decimal

from engine.base import ExitModule
from engine.domain import Position, View, Vote


class VolumeDryUp(ExitModule):
    """Assechement du volume : le volume moyen des `length` dernieres barres tombe sous `ratio`
    fois celui des `period` barres qui les precedent. Vote alors la fermeture, sinon s'abstient. Sans volume
    de reference, s'abstient.

    Intensite : 1 - volume recent / (ratio x volume de reference), entre 0 et 1.
    """

    def __init__(self, length: int, period: int, ratio: Decimal):
        self.name = f"VolumeDryUp({length},{period},{ratio})"
        self.warmup = length + period
        self.length = length
        self.period = period
        self.ratio = ratio

    def vote(self, view: View, position: Position) -> Vote | None:
        bars = view.bars[-self.warmup:]
        recent = sum((bar.volume for bar in bars[-self.length:]), Decimal(0)) / self.length
        reference = sum((bar.volume for bar in bars[:self.period]), Decimal(0)) / self.period
        if reference == 0 or recent >= self.ratio * reference:
            return None
        return Vote(1, 1 - recent / (self.ratio * reference))
