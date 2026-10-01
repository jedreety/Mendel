from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class HourOfDay(Rule):
    """Vote `direction` quand la prochaine barre commence dans la plage horaire UTC [start, end).

    Hors plage, s'abstient. La plage peut passer minuit : start=22, end=2.
    Exemple : l'anomalie 21 h - 23 h UTC du Bitcoin (Quantpedia, donnees Gemini 2015-2022, avant couts).
    Intensite fixe : 1.
    """

    def __init__(self, weight: Decimal, start: int, end: int, direction: int):
        self.name = f"HourOfDay({start}-{end},{direction:+d})"
        self.weight = weight
        self.warmup = 1
        self.start = start
        self.end = end
        self.direction = direction

    def vote(self, view: View) -> Vote | None:
        hour = view.bars[-1].time.hour
        if self.start <= self.end:
            inside = self.start <= hour < self.end
        else:
            inside = hour >= self.start or hour < self.end
        return Vote(self.direction, Decimal(1)) if inside else None
