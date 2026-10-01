from decimal import Decimal

from engine.base import ExitBudget, Sizer
from engine.domain import Portfolio, Tally, View


class FractionalKelly(Sizer):
    """Critere de Kelly (1956) fractionnaire : le capital perdu sur un stop touche vaut `fraction` de la
    mise de Kelly, p - (1 - p) / b.

    b : rapport gain sur perte des caps, le target_ratio du budget, avant frais.
    p : score de l'interpreteur ramene a une probabilite, (1 + score) / 2. Ce n'est pas une probabilite
    calibree : tant que la frequence de gain reelle par niveau de score n'est pas mesuree, la taille
    repose sur une hypothese.
    Mise de Kelly nulle ou negative : quantite nulle, que la decision journalise comme notionnel sous le minimum.
    """

    def __init__(self, budget: ExitBudget, fraction: Decimal):
        self.budget = budget
        self.fraction = fraction
        self.warmup = budget.warmup

    def size(self, view: View, portfolio: Portfolio, price: Decimal, tally: Tally) -> Decimal:
        p = (1 + tally.score) / 2
        kelly = max(Decimal(0), p - (1 - p) / self.budget.target_ratio)
        return portfolio.cash * self.fraction * kelly / self.budget.stop_distance(view, price)
