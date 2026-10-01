from datetime import timedelta
from decimal import Decimal

from engine.base import RiskRule
from engine.domain import Portfolio, RiskVerdict, View


class Cooldown(RiskRule):
    """Refuse toute entree pendant `hours` heures apres une sortie."""

    def __init__(self, hours: int):
        self.name = f"Cooldown({hours}h)"
        self.warmup = 0
        self.pause = timedelta(hours=hours)

    def check(self, view: View, portfolio: Portfolio) -> RiskVerdict:
        if portfolio.last_exit is not None and view.bars[-1].time - portfolio.last_exit < self.pause:
            return RiskVerdict(self.name, Decimal(0), "pause apres sortie")
        return RiskVerdict(self.name, Decimal(1), "hors pause")
