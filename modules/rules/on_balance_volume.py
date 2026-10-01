from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class OnBalanceVolume(Rule):
    """Pente de l'OBV sur `period` barres : volume compte en plus quand la cloture monte, en moins
    quand elle baisse. Vote le signe, 0 a l'equilibre, s'abstient sans volume.

    Intensite : volume signe rapporte au volume total, entre 0 et 1.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"OnBalanceVolume({period})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period - 1:]
        flow = total = Decimal(0)
        for prev, bar in zip(bars, bars[1:]):
            total += bar.volume
            if bar.close > prev.close:
                flow += bar.volume
            elif bar.close < prev.close:
                flow -= bar.volume
        if total == 0:
            return None
        if flow == 0:
            return Vote(0, Decimal(0))
        return Vote(1 if flow > 0 else -1, abs(flow) / total)
