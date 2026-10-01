from decimal import Decimal

from engine.base import ExitBudget
from engine.domain import View


class VolatilityBudget(ExitBudget):
    """Budget de sortie en unites de volatilite.

    patience multiplie la distance de stop et la duree maximale, jamais le plancher.
    """

    FLOOR = Decimal("0.05")  # plancher absolu : la distance ne depasse jamais 5 % du prix

    def __init__(self, stop_vol: Decimal, target_ratio: Decimal, max_hold_bars: int, patience: Decimal, vol_period: int):
        self.stop_vol = stop_vol
        self.target_ratio = target_ratio
        self.max_hold_bars = max_hold_bars
        self.patience = patience
        self.vol_period = vol_period
        self.warmup = vol_period + 1

    def stop_distance(self, view: View, price: Decimal) -> Decimal:
        return min(self.stop_vol * self.patience * view.volatility(self.vol_period), self.FLOOR * price)

    def hold_limit(self) -> Decimal:
        return self.max_hold_bars * self.patience
