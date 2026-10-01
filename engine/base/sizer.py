from abc import ABC, abstractmethod
from decimal import Decimal

from engine.domain import Portfolio, Tally, View


class Sizer(ABC):
    """Dimensionneur. Lit la distance de stop dans le budget de sortie, ne la recalcule jamais.

    tally : decision de l'interpreteur qui motive l'entree ; son score mesure la confiance.
    """

    warmup: int

    @abstractmethod
    def size(self, view: View, portfolio: Portfolio, price: Decimal, tally: Tally) -> Decimal:
        """Quantite brute pour une entree a `price`, avant risque et contraintes du lieu d'execution."""
