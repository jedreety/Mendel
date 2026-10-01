from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Tally:
    """Resultat de l'interpreteur.

    direction: +1, -1, ou 0 si aucune direction n'est retenue.
    expressed: poids des regles qui ont vote. enrolled: poids inscrit.
    """

    direction: int
    score: Decimal
    expressed: Decimal
    enrolled: Decimal
    reason: str
