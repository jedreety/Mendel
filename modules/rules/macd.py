from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


def _ema(values: list[Decimal], period: int) -> list[Decimal]:
    """Moyenne exponentielle amorcee par la moyenne simple des `period` premieres valeurs."""
    alpha = Decimal(2) / (period + 1)
    current = sum(values[:period], Decimal(0)) / period
    series = [current]
    for value in values[period:]:
        current += alpha * (value - current)
        series.append(current)
    return series


class Macd(Rule):
    """MACD : histogramme (ligne MACD moins sa ligne de signal) positif +1, negatif -1.

    Les moyennes exponentielles portent sur une fenetre fixe de 3 x slow + signal barres, amorcees
    par une moyenne simple : le vote ne depend pas de la taille de la vue.
    Intensite : histogramme en unites de volatilite (periode slow), plafonne a 1.
    """

    def __init__(self, weight: Decimal, fast: int, slow: int, signal: int):
        self.name = f"Macd({fast},{slow},{signal})"
        self.weight = weight
        self.warmup = 3 * slow + signal
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def vote(self, view: View) -> Vote | None:
        closes = [bar.close for bar in view.bars[-self.warmup:]]
        fast = _ema(closes, self.fast)
        slow = _ema(closes, self.slow)
        line = [f - s for f, s in zip(fast[-len(slow):], slow)]
        histogram = line[-1] - _ema(line, self.signal)[-1]
        if histogram == 0:
            return Vote(0, Decimal(0))
        r = view.volatility(self.slow)
        if r == 0:
            return None
        return Vote(1 if histogram > 0 else -1, min(Decimal(1), abs(histogram) / r))
