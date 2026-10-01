from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class FractalBreakout(Rule):
    """Cassure de fractale de Bill Williams : cloture au-dessus de la derniere fractale haute confirmee +1,
    sous la derniere fractale basse confirmee -1, sinon s'abstient.

    Fractale haute : plus haut strictement superieur a ceux des deux barres de chaque cote ; basse, en miroir.
    Elle n'est confirmee qu'une fois closes les deux barres qui la suivent. Recherche sur les `window` dernieres
    barres. Si les deux sont franchies, la plus recente l'emporte.
    Intensite : depassement en unites de volatilite (periode window), plafonne a 1.
    """

    def __init__(self, weight: Decimal, window: int):
        self.name = f"FractalBreakout({window})"
        self.weight = weight
        self.warmup = window + 1
        self.window = window

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.window:]
        close = bars[-1].close
        high_seen = low_seen = False
        for i in range(len(bars) - 3, 1, -1):
            bar, around = bars[i], bars[i - 2:i] + bars[i + 1:i + 3]
            if not high_seen and all(bar.high > other.high for other in around):
                if close > bar.high:
                    return Vote(1, min(Decimal(1), (close - bar.high) / view.volatility(self.window)))
                high_seen = True
            if not low_seen and all(bar.low < other.low for other in around):
                if close < bar.low:
                    return Vote(-1, min(Decimal(1), (bar.low - close) / view.volatility(self.window)))
                low_seen = True
            if high_seen and low_seen:
                return None
        return None
