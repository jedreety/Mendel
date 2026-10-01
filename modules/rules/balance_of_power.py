from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class BalanceOfPower(Rule):
    """Balance of Power de Livshin : moyenne sur `period` barres de (cloture - ouverture) / amplitude.
    Vote le signe, 0 a l'equilibre. Une barre sans amplitude compte pour 0.

    Intensite : |BOP|, entre 0 et 1.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"BalanceOfPower({period})"
        self.weight = weight
        self.warmup = period
        self.period = period

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period:]
        balance = sum((bar.body / bar.range for bar in bars if bar.range > 0), Decimal(0)) / self.period
        if balance == 0:
            return Vote(0, Decimal(0))
        return Vote(1 if balance > 0 else -1, abs(balance))
