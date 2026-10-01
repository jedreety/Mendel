from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Trade:
    """Trade clos, inscrit au grand livre. net = resultat brut moins frais d'entree et de sortie."""

    entry_time: datetime
    exit_time: datetime
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    fees: Decimal
    net: Decimal
    reason: str
