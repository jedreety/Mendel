from datetime import timedelta
from decimal import Decimal

from engine.base import RiskRule
from engine.domain import Portfolio, RiskVerdict, View


class LossCooldown(RiskRule):
    """Refuse toute entree pendant `hours` heures apres un trade perdant, frais compris.

    Un trade gagnant ne declenche aucune pause : pour une pause apres toute sortie, voir Cooldown.
    """

    def __init__(self, hours: int):
        self.name = f"LossCooldown({hours}h)"
        self.warmup = 0
        self.pause = timedelta(hours=hours)

    def check(self, view: View, portfolio: Portfolio) -> RiskVerdict:
        if portfolio.trades:
            last = portfolio.trades[-1]
            if last.net < 0 and view.bars[-1].time - last.exit_time < self.pause:
                return RiskVerdict(self.name, Decimal(0), "pause apres perte")
        return RiskVerdict(self.name, Decimal(1), "hors pause")
