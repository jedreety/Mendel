import calendar
from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class DayOfMonth(Rule):
    """Vote `direction` quand la prochaine barre commence un des jours `days` du mois, en UTC.

    Jours positifs depuis le debut du mois (1 = premier jour), negatifs depuis la fin (-1 = dernier jour).
    Les autres jours, s'abstient.
    Exemple : l'effet de tournant du mois, du dernier jour aux trois premiers (Lakonishok et Smidt,
    Review of Financial Studies, 1988, sur le Dow Jones).
    Intensite fixe : 1.
    """

    def __init__(self, weight: Decimal, days: tuple[int, ...], direction: int):
        self.name = f"DayOfMonth({','.join(str(day) for day in days)},{direction:+d})"
        self.weight = weight
        self.warmup = 1
        self.days = days
        self.direction = direction

    def vote(self, view: View) -> Vote | None:
        time = view.bars[-1].time
        last = calendar.monthrange(time.year, time.month)[1]
        if time.day in self.days or time.day - last - 1 in self.days:
            return Vote(self.direction, Decimal(1))
        return None
