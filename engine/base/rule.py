from abc import ABC, abstractmethod
from decimal import Decimal

from engine.domain import View, Vote


class Rule(ABC):
    """Regle d'entree. Produit un avis, ne passe jamais d'ordre.

    weight : confiance statique, fixee dans le fichier de strategie.
    warmup : barres necessaires ; en dessous, la regle s'abstient d'office.
    """

    name: str
    weight: Decimal
    warmup: int

    @abstractmethod
    def vote(self, view: View) -> Vote | None:
        """Renvoie un avis, ou None pour s'abstenir."""
