from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal


@dataclass(frozen=True)
class Venue:
    """Contraintes et couts du lieu d'execution.

    fee_rate : taux le plus defavorable, par cote. slippage : fraction du prix, jamais nulle.
    """

    tick_size: Decimal
    qty_step: Decimal
    min_notional: Decimal
    fee_rate: Decimal
    slippage: Decimal

    def fill_price(self, price: Decimal, side: str) -> Decimal:
        """Prix d'execution suppose : glissement et arrondi au pas de prix, tous deux defavorables."""
        if side == "buy":
            ticks = (price * (1 + self.slippage) / self.tick_size).to_integral_value(rounding=ROUND_CEILING)
        else:
            ticks = (price * (1 - self.slippage) / self.tick_size).to_integral_value(rounding=ROUND_FLOOR)
        return ticks * self.tick_size
