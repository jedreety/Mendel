from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class DayOfWeek(Rule):
    """Vote `direction` quand la prochaine barre commence un des jours `days` (0 = lundi, en UTC).

    Les autres jours, s'abstient.
    Exemple : l'effet lundi du Bitcoin (Caporale et Plastun, Finance Research Letters, 2019).
    Intensite fixe : 1.
    """

    def __init__(self, weight: Decimal, days: tuple[int, ...], direction: int):
        self.name = f"DayOfWeek({','.join(str(day) for day in days)},{direction:+d})"
        self.weight = weight
        self.warmup = 1
        self.days = days
        self.direction = direction

    def vote(self, view: View) -> Vote | None:
        if view.bars[-1].time.weekday() in self.days:
            return Vote(self.direction, Decimal(1))
        return None
