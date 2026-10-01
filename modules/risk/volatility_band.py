from decimal import Decimal

from engine.base import RiskRule
from engine.domain import Portfolio, RiskVerdict, View


class VolatilityBand(RiskRule):
    """Refuse l'entree quand la volatilite (periode `period`), rapportee au prix, sort de [minimum, maximum].

    Sous le minimum, le mouvement typique d'une barre ne couvre pas l'aller-retour.
    """

    def __init__(self, period: int, minimum: Decimal, maximum: Decimal):
        self.name = f"VolatilityBand({period},{minimum},{maximum})"
        self.warmup = period + 1
        self.period = period
        self.minimum = minimum
        self.maximum = maximum

    def check(self, view: View, portfolio: Portfolio) -> RiskVerdict:
        ratio = view.volatility(self.period) / view.bars[-1].close
        if ratio < self.minimum:
            return RiskVerdict(self.name, Decimal(0), "volatilite sous le minimum")
        if ratio > self.maximum:
            return RiskVerdict(self.name, Decimal(0), "volatilite au-dessus du maximum")
        return RiskVerdict(self.name, Decimal(1), "volatilite dans la bande")
