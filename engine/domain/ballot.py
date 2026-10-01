from dataclasses import dataclass
from decimal import Decimal

from engine.domain.vote import Vote


@dataclass(frozen=True)
class Ballot:
    """Bulletin d'une regle : son nom, son poids inscrit, son vote ou None si elle s'abstient."""

    name: str
    weight: Decimal
    vote: Vote | None
