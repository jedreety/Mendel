from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class CandleStreak(Rule):
    """Serie de `length` bougies de meme couleur : vote la couleur de la serie, sinon s'abstient.

    Intensite : deplacement net de la serie rapporte a son amplitude totale.
    """

    def __init__(self, weight: Decimal, length: int):
        self.name = f"CandleStreak({length})"
        self.weight = weight
        self.warmup = length
        self.length = length

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.length:]
        if all(bar.body > 0 for bar in bars):
            direction = 1
        elif all(bar.body < 0 for bar in bars):
            direction = -1
        else:
            return None
        move = abs(bars[-1].close - bars[0].open)
        span = max(bar.high for bar in bars) - min(bar.low for bar in bars)
        return Vote(direction, move / span)
