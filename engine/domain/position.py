from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from engine.domain.caps import Caps


@dataclass(frozen=True)
class Position:
    """Position longue ouverte : le comptant ne permet pas la vente a decouvert.

    bars_held : barres closes depuis l'entree. caps : caps en vigueur chez le courtier.
    peak : extreme favorable depuis l'entree (plus haut). advances : barres qui ont fait un nouveau plus haut.
    """

    quantity: Decimal
    entry_price: Decimal
    entry_time: datetime
    entry_fee: Decimal
    bars_held: int
    caps: Caps | None
    peak: Decimal
    advances: int
