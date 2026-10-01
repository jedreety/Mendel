from decimal import Decimal

from engine.base import Bedrock, RiskRule
from engine.domain import Portfolio, RiskVerdict, View


class CostCover(RiskRule):
    """Refuse l'entree quand le gain vise ne couvre pas `multiple` fois le cout d'un aller-retour.

    Gain vise : ecart entre le cap positif et le prix, pour une entree a la derniere cloture. Les caps
    viennent du socle de la strategie, a qui le fichier de strategie passe la meme instance.
    cost : cout d'un aller-retour en fraction du prix, frais et glissement des deux cotes.
    Avec VENUE de run.py, 2 x (fee_rate + slippage). La valeur est declaree ici : a relire avec le lieu.
    """

    def __init__(self, bedrock: Bedrock, cost: Decimal, multiple: Decimal):
        self.name = f"CostCover({cost},{multiple})"
        self.warmup = bedrock.warmup
        self.bedrock = bedrock
        self.cost = cost
        self.multiple = multiple

    def check(self, view: View, portfolio: Portfolio) -> RiskVerdict:
        close = view.bars[-1].close
        gain = self.bedrock.caps(view, close).target - close
        if gain < self.multiple * self.cost * close:
            return RiskVerdict(self.name, Decimal(0), "gain vise sous le cout")
        return RiskVerdict(self.name, Decimal(1), "gain vise au-dessus du cout")
