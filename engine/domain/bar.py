from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Bar:
    """Barre close. `time` est l'instant de cloture, en UTC."""

    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    @property
    def body(self) -> Decimal:
        """Corps signe : positif pour une bougie verte, negatif pour une rouge."""
        return self.close - self.open

    @property
    def range(self) -> Decimal:
        return self.high - self.low

    @property
    def upper_shadow(self) -> Decimal:
        return self.high - max(self.open, self.close)

    @property
    def lower_shadow(self) -> Decimal:
        return min(self.open, self.close) - self.low
