from dataclasses import dataclass
from decimal import Decimal

from engine.domain.bar import Bar


@dataclass(frozen=True)
class View:
    """Vue figee du monde, en lecture seule. La derniere barre est la derniere barre close."""

    symbol: str
    bars: tuple[Bar, ...]

    def volatility(self, period: int) -> Decimal:
        """True range moyen sur `period` barres, en unites de prix. Exige period + 1 barres."""
        window = self.bars[-period - 1:]
        ranges = (max(bar.high, prev.close) - min(bar.low, prev.close) for prev, bar in zip(window, window[1:]))
        return sum(ranges, Decimal(0)) / period
