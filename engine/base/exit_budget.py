from abc import ABC, abstractmethod
from decimal import Decimal

from engine.domain import View


class ExitBudget(ABC):
    """Budget de sortie. Seul endroit ou la distance de stop est calculee.

    Le socle et le dimensionneur recoivent la meme instance, injectee par le fichier de strategie.
    target_ratio : le cap positif vaut ce multiple de la distance de stop.
    """

    warmup: int
    target_ratio: Decimal

    @abstractmethod
    def stop_distance(self, view: View, price: Decimal) -> Decimal:
        """Distance de stop en unites de prix, plancher absolu compris."""

    @abstractmethod
    def hold_limit(self) -> Decimal:
        """Duree maximale de detention, en barres, patience comprise."""
