from decimal import Decimal

from engine.base import RiskRule
from engine.domain import Portfolio, RiskVerdict, View


class Choppiness(RiskRule):
    """Refuse l'entree quand l'indice de choppiness de Dreiss sur `period` barres depasse `maximum` :
    le marche oscille sans avancer.

    CI = 100 x log10(somme des true ranges / amplitude des `period` barres) / log10(period).
    Proche de 100, oscillation pure ; proche de 0, tendance pure. Seuil usuel : 61.8.
    period vaut au moins 2. Amplitude nulle : refus.
    """

    def __init__(self, period: int, maximum: Decimal):
        self.name = f"Choppiness({period},{maximum})"
        self.warmup = period + 1
        self.period = period
        self.maximum = maximum

    def check(self, view: View, portfolio: Portfolio) -> RiskVerdict:
        bars = view.bars[-self.period:]
        span = max(bar.high for bar in bars) - min(bar.low for bar in bars)
        if span == 0:
            return RiskVerdict(self.name, Decimal(0), "amplitude nulle")
        ranges = self.period * view.volatility(self.period)
        index = 100 * (ranges / span).log10() / Decimal(self.period).log10()
        if index > self.maximum:
            return RiskVerdict(self.name, Decimal(0), "marche sans tendance")
        return RiskVerdict(self.name, Decimal(1), "marche directionnel")
