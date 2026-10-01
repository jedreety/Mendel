from datetime import timedelta
from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class PreviousDayRange(Rule):
    """Cassure de l'amplitude de la veille UTC : cloture au-dessus de son plus haut +1, sous son plus bas -1,
    entre les deux s'abstient.

    La veille est le jour UTC qui precede celui ou commence la prochaine barre ; ses barres sont celles qui
    closent apres son debut et au plus tard a sa fin. window : barres parcourues ; si elles ne couvrent pas
    toute la veille, s'abstient. Veille sans amplitude : s'abstient.
    Intensite : depassement rapporte a l'amplitude de la veille, plafonne a 1.
    """

    def __init__(self, weight: Decimal, window: int):
        self.name = f"PreviousDayRange({window})"
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
        close = bars[-1].close
        if close > high:
            return Vote(1, min(Decimal(1), (close - high) / (high - low)))
        if close < low:
            return Vote(-1, min(Decimal(1), (low - close) / (high - low)))
        return None
