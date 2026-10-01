from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class ChaikinMoneyFlow(Rule):
    """Chaikin Money Flow sur `period` barres : position de chaque cloture dans son amplitude,
    ponderee par le volume. Vote le signe, 0 a l'equilibre, s'abstient sans volume.

    Intensite : |CMF|, entre 0 et 1.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"ChaikinMoneyFlow({period})"
        self.weight = weight
        self.warmup = period
        self.period = period

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period:]
        volume = sum((bar.volume for bar in bars), Decimal(0))
        if volume == 0:
            return None
        flow = sum(
            (((bar.close - bar.low) - (bar.high - bar.close)) / bar.range * bar.volume for bar in bars if bar.range > 0),
            Decimal(0),
        )
        cmf = flow / volume
        if cmf == 0:
            return Vote(0, Decimal(0))
        return Vote(1 if cmf > 0 else -1, abs(cmf))
