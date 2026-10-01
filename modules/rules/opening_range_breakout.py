from datetime import timedelta
from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class OpeningRangeBreakout(Rule):
    """Seuil de la premiere bougie : cassure du plus haut ou du plus bas des `length` premieres barres d'une
    seance a heure fixe UTC. Cloture au-dessus +1, en dessous -1, entre les deux s'abstient.

    La crypto n'ouvre jamais : la seance est une convention, et sa premiere barre est definie
    comme dans SessionOpen. Le vote vaut de la fin du range jusqu'a l'ouverture suivante ; pendant le range,
    s'abstient. window : barres parcourues pour retrouver l'ouverture ; au-dela, s'abstient.
    Range sans amplitude : s'abstient.
    Intensite : depassement rapporte a l'amplitude du range, plafonne a 1.
    """

    def __init__(self, weight: Decimal, hour: int, minute: int, length: int, window: int):
        self.name = f"OpeningRangeBreakout({hour:02d}:{minute:02d},{length})"
        self.weight = weight
        self.warmup = window
        self.hour = hour
        self.minute = minute
        self.length = length

    def vote(self, view: View) -> Vote | None:
        last = view.bars[-1].time
        start = last.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        if start >= last:
            start -= timedelta(days=1)
        bars = view.bars[-self.warmup:]
        for index, (prev, bar) in enumerate(zip(bars, bars[1:])):
            if prev.time <= start < bar.time:
                session = bars[index + 1:]
                if len(session) <= self.length:
                    return None
                high = max(b.high for b in session[:self.length])
                low = min(b.low for b in session[:self.length])
                if high == low:
                    return None
                close = session[-1].close
                if close > high:
                    return Vote(1, min(Decimal(1), (close - high) / (high - low)))
                if close < low:
                    return Vote(-1, min(Decimal(1), (low - close) / (high - low)))
                return None
        return None
