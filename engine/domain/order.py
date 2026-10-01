from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Order:
    """Ordre au marche. `id` est deterministe : un reessai ne double jamais l'ordre. side : "buy" ou "sell"."""

    id: str
    side: str
    quantity: Decimal
    reason: str
