from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from engine.domain.position import Position
from engine.domain.trade import Trade


@dataclass(frozen=True)
class Portfolio:
    """Etat du portefeuille remis a la decision. last_exit : instant de la derniere sortie : aucune entree sur sa barre.

    trades : trades clos, du plus ancien au plus recent. Les modules y lisent le resultat du jour,
    les series de pertes ou le drawdown realise.
    """

    cash: Decimal
    position: Position | None
    last_exit: datetime | None
    trades: tuple[Trade, ...]
