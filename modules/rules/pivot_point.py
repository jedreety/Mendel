from datetime import timedelta
from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class PivotPoint(Rule):
    """Point pivot classique de la veille UTC, (plus haut + plus bas + cloture) / 3 : cloture au-dessus +1,
    en dessous -1, dessus 0.

    La veille est definie comme dans PreviousDayRange. window : barres parcourues ; si elles ne couvrent pas
    toute la veille, s'abstient. Veille sans amplitude : s'abstient.
    Intensite : distance au pivot rapportee a sa distance a la premiere resistance (2P - plus bas) ou au premier
    support (2P - plus haut), plafonnee a 1.
    """

    def __init__(self, weight: Decimal, window: int):
        self.name = f"PivotPoint({window})"
        self.weight = weight
        self.warmup = window

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.warmup:]
        end = bars[-1].time.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=1)
        if bars[0].time > start:
            return None
        day = [bar for bar in bars if start < bar.time <= end]
        if not day:
            return None
        high = max(bar.high for bar in day)
        low = min(bar.low for bar in day)
        if high == low:
            return None
        pivot = (high + low + day[-1].close) / 3
        close = bars[-1].close
        if close > pivot:
            return Vote(1, min(Decimal(1), (close - pivot) / (pivot - low)))
        if close < pivot:
            return Vote(-1, min(Decimal(1), (pivot - close) / (high - pivot)))
        return Vote(0, Decimal(0))
