from decimal import Decimal

from engine.base import RiskRule
from engine.domain import Portfolio, RiskVerdict, View


class DailyGainLock(RiskRule):
    """Refuse toute nouvelle entree une fois que les trades clos du jour ont rapporte au moins `limit`
    du capital du debut de journee (0.02 pour 2 %), frais compris : le gain du jour est mis a l'abri.

    Le jour est celui, en UTC, ou commence la prochaine barre. Un trade compte le jour de sa sortie.
    Capital du debut de journee : comptant moins le resultat net du jour ; une entree se decide a plat.
    """

    def __init__(self, limit: Decimal):
        self.name = f"DailyGainLock({limit})"
        self.warmup = 0
        self.limit = limit

    def check(self, view: View, portfolio: Portfolio) -> RiskVerdict:
        today = view.bars[-1].time.date()
        net = Decimal(0)
        for trade in reversed(portfolio.trades):
            if trade.exit_time.date() < today:
                break
            net += trade.net
        if net >= self.limit * (portfolio.cash - net):
            return RiskVerdict(self.name, Decimal(0), "gain du jour atteint")
        return RiskVerdict(self.name, Decimal(1), "gain du jour sous la limite")
