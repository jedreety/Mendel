from decimal import Decimal

from engine.base import ExitBudget, Sizer
from engine.domain import Portfolio, Tally, View


class ConfidenceRisk(Sizer):
    """Taille telle qu'un stop touche coute une fraction du capital qui grandit avec la confiance :
    `minimum` pour un score nul, `maximum` pour un score de 1, lineaire entre les deux.

    Confiance : valeur absolue du score de l'interpreteur. Elle fait varier le budget de risque d'un trade
    a l'autre ; la volatilite, elle, reste absorbee par la taille.
    """

    def __init__(self, budget: ExitBudget, minimum: Decimal, maximum: Decimal):
        self.budget = budget
        self.minimum = minimum
        self.maximum = maximum
        self.warmup = budget.warmup

    def size(self, view: View, portfolio: Portfolio, price: Decimal, tally: Tally) -> Decimal:
        fraction = self.minimum + (self.maximum - self.minimum) * abs(tally.score)
        return portfolio.cash * fraction / self.budget.stop_distance(view, price)
