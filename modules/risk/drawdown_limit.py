from decimal import Decimal

from engine.base import RiskRule
from engine.domain import Portfolio, RiskVerdict, View


class DrawdownLimit(RiskRule):
    """Applique `factor` a la taille (0 refuse) quand le capital realise est a au moins `limit` sous son
    plus haut (0.1 pour 10 %).

    Capital realise : le comptant, puisqu'une entree se decide a plat. Son historique se reconstruit
    a rebours depuis les trades clos, capital initial compris.
    """

    def __init__(self, limit: Decimal, factor: Decimal):
        self.name = f"DrawdownLimit({limit},{factor})"
        self.warmup = 0
        self.limit = limit
        self.factor = factor

    def check(self, view: View, portfolio: Portfolio) -> RiskVerdict:
        equity = peak = portfolio.cash
        for trade in reversed(portfolio.trades):
            equity -= trade.net
            peak = max(peak, equity)
        if portfolio.cash <= (1 - self.limit) * peak:
            return RiskVerdict(self.name, self.factor, "drawdown au-dela de la limite")
        return RiskVerdict(self.name, Decimal(1), "drawdown sous la limite")
