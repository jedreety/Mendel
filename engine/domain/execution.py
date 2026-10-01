from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Execution:
    """Execution d'un ordre, frais en monnaie de cotation. reason : ce qui a motive l'ordre."""

    order_id: str
    time: datetime
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    reason: str
