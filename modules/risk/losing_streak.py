from decimal import Decimal

from engine.base import RiskRule
from engine.domain import Portfolio, RiskVerdict, View


class LosingStreak(RiskRule):
    """Applique `factor` a la taille (0 refuse) apres au moins `length` trades perdants d'affilee, frais compris.

    Le risque reduit, il ne grossit jamais : augmenter la mise apres une perte pour se refaire
    est une martingale, excellente en backtest jusqu'a la ruine.
    """

    def __init__(self, length: int, factor: Decimal):
        self.name = f"LosingStreak({length},{factor})"
        self.warmup = 0
        self.length = length
        self.factor = factor

    def check(self, view: View, portfolio: Portfolio) -> RiskVerdict:
        streak = 0
        for trade in reversed(portfolio.trades):
            if trade.net >= 0:
                break
            streak += 1
        if streak >= self.length:
            return RiskVerdict(self.name, self.factor, "serie de pertes")
        return RiskVerdict(self.name, Decimal(1), "pas de serie de pertes")
