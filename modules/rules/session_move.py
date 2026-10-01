from datetime import timedelta
from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class SessionMove(Rule):
    """Sens du mouvement depuis l'ouverture d'une seance a heure fixe UTC : momentum intraday.

    Shen, Urquhart et Wang (Financial Review, 2022) trouvent que la premiere demi-heure du Bitcoin
    predit positivement la derniere. La seance suit la meme convention que SessionOpen.
    window : barres parcourues pour retrouver l'ouverture ; au-dela, s'abstient.
    Intensite : deplacement depuis l'ouverture rapporte a l'amplitude de la seance.
    """

    def __init__(self, weight: Decimal, hour: int, minute: int, window: int):
        self.name = f"SessionMove({hour:02d}:{minute:02d})"
        self.weight = weight
        self.warmup = window
        self.hour = hour
        self.minute = minute

    def vote(self, view: View) -> Vote | None:
        last = view.bars[-1].time
        start = last.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        if start >= last:
            start -= timedelta(days=1)
        bars = view.bars[-self.warmup:]
        for index, (prev, bar) in enumerate(zip(bars, bars[1:])):
            if prev.time <= start < bar.time:
                session = bars[index + 1:]
                move = session[-1].close - session[0].open
                if move == 0:
                    return Vote(0, Decimal(0))
                span = max(b.high for b in session) - min(b.low for b in session)
                return Vote(1 if move > 0 else -1, abs(move) / span)
        return None
