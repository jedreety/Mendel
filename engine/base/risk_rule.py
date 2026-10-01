from abc import ABC, abstractmethod

from engine.domain import Portfolio, RiskVerdict, View


class RiskRule(ABC):
    """Regle de risque. Ne vote pas : refuse ou reduit la taille, apres la direction.

    warmup : barres necessaires ; aucune entree avant.
    """

    name: str
    warmup: int

    @abstractmethod
    def check(self, view: View, portfolio: Portfolio) -> RiskVerdict:
        """Verdict sur une entree envisagee."""
