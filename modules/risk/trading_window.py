from decimal import Decimal

from engine.base import RiskRule
from engine.domain import Portfolio, RiskVerdict, View


class TradingWindow(RiskRule):
    """Refuse l'entree hors des jours `days` (0 = lundi) et de la plage horaire UTC [start, end).

    La plage peut passer minuit : start=22, end=2.
    """

    def __init__(self, days: tuple[int, ...], start: int, end: int):
        self.name = f"TradingWindow({','.join(str(day) for day in days)},{start}-{end})"
        self.warmup = 0
        self.days = days
        self.start = start
        self.end = end

    def check(self, view: View, portfolio: Portfolio) -> RiskVerdict:
        time = view.bars[-1].time
        if self.start <= self.end:
            hours = self.start <= time.hour < self.end
        else:
            hours = time.hour >= self.start or time.hour < self.end
        if time.weekday() in self.days and hours:
            return RiskVerdict(self.name, Decimal(1), "dans la fenetre")
        return RiskVerdict(self.name, Decimal(0), "hors fenetre")
