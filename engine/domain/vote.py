from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Vote:
    """Avis d'une regle ou d'un module de sortie.

    direction: +1 ou -1, ou 0 pour "ne rien faire", qui reste au denominateur.
    En sortie, +1 vote la fermeture et -1 retient la position.
    intensity: force du signal a cet instant, entre 0 et 1.
    Une abstention n'est pas un Vote : c'est None.
    """

    direction: int
    intensity: Decimal
