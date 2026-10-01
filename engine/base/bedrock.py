from abc import ABC, abstractmethod
from decimal import Decimal

from engine.domain import Caps, Position, View


class Bedrock(ABC):
    """Socle de risque. Etage zero de la sortie, argument distinct de HardTier.

    Ses caps existent aussi comme ordres conditionnels chez le courtier : ils protegent la position meme si le processus s'arrete.
    """

    warmup: int

    @abstractmethod
    def caps(self, view: View, entry_price: Decimal) -> Caps:
        """Caps autour du prix d'entree, avec la volatilite du moment."""

    @abstractmethod
    def check(self, view: View, position: Position) -> str | None:
        """"stop" ou "target" si la derniere barre a touche un cap en vigueur, sinon None."""
