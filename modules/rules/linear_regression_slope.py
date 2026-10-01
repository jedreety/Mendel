from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class LinearRegressionSlope(Rule):
    """Signe de la pente de la regression lineaire des clotures sur `period` barres.

    Intensite : deplacement ajuste sur la periode, en unites de volatilite ramenees a l'horizon
    par racine de period, plafonne a 1.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"LinearRegressionSlope({period})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period

    def vote(self, view: View) -> Vote | None:
        closes = [bar.close for bar in view.bars[-self.period:]]
        x_mean = Decimal(self.period - 1) / 2
        y_mean = sum(closes, Decimal(0)) / self.period
        covariance = sum(((i - x_mean) * (close - y_mean) for i, close in enumerate(closes)), Decimal(0))
        variance = sum(((i - x_mean) ** 2 for i in range(self.period)), Decimal(0))
        slope = covariance / variance
        if slope == 0:
            return Vote(0, Decimal(0))
        move = abs(slope) * (self.period - 1)
        scale = view.volatility(self.period) * Decimal(self.period).sqrt()
        return Vote(1 if slope > 0 else -1, min(Decimal(1), move / scale))
