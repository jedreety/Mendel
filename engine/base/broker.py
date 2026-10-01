from abc import ABC, abstractmethod
from decimal import Decimal

from engine.domain import Bar, Caps, Execution, Order


class Broker(ABC):
    """Courtier. Seule la couche d'execution lui parle."""

    @abstractmethod
    def on_bar(self, bar: Bar) -> list[Execution]:
        """Signale la cloture de `bar`. Renvoie les executions survenues pendant la barre."""

    @abstractmethod
    def submit(self, order: Order) -> Execution:
        """Envoie un ordre au marche et renvoie son execution."""

    @abstractmethod
    def protect(self, order_id: str, quantity: Decimal, caps: Caps) -> None:
        """Pose ou remplace les ordres conditionnels de protection."""

    @abstractmethod
    def unprotect(self) -> None:
        """Annule les ordres de protection."""
