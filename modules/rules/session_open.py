from datetime import timedelta
from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class SessionOpen(Rule):
    """Couleur de la bougie d'ouverture d'une seance a heure fixe UTC : verte +1, rouge -1, sans corps 0.

    La crypto n'ouvre jamais : la seance est une convention, par exemple 0 h UTC,
    ou 13 h 30 UTC pour l'ouverture de New York en heure d'ete (14 h 30 en hiver, sans ajustement ici).
    La bougie d'ouverture est la premiere qui clot apres l'instant d'ouverture. Son vote vaut
    jusqu'a l'ouverture suivante. window : barres parcourues pour la retrouver ; au-dela, s'abstient.
    Intensite : part du corps dans l'amplitude de la bougie.
    """

    def __init__(self, weight: Decimal, hour: int, minute: int, window: int):
        self.name = f"SessionOpen({hour:02d}:{minute:02d})"
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
        for prev, bar in zip(bars, bars[1:]):
            if prev.time <= start < bar.time:
                if bar.body == 0:
                    return Vote(0, Decimal(0))
                return Vote(1 if bar.body > 0 else -1, abs(bar.body) / bar.range)
        return None
