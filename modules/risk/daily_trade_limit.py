from decimal import Decimal

from engine.base import RiskRule
from engine.domain import Portfolio, RiskVerdict, View


class DailyTradeLimit(RiskRule):
    """Refuse l'entree une fois `count` trades ouverts dans la journee.

    Le jour est celui, en UTC, ou commence la prochaine barre. Un trade compte le jour de son entree.
    """

    def __init__(self, count: int):
        self.name = f"DailyTradeLimit({count})"
        self.warmup = 0
        self.count = count

    def check(self, view: View, portfolio: Portfolio) -> RiskVerdict:
        today = view.bars[-1].time.date()
        opened = 0
        for trade in reversed(portfolio.trades):
            if trade.entry_time.date() < today:
                break
            opened += 1
        if opened >= self.count:
            return RiskVerdict(self.name, Decimal(0), "nombre de trades du jour atteint")
        return RiskVerdict(self.name, Decimal(1), "nombre de trades du jour sous la limite")
