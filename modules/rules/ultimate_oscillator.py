from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class UltimateOscillator(Rule):
    """Ultimate Oscillator de Larry Williams, lu en retour a la moyenne : sous `lower` +1, au-dessus de
    `upper` -1, entre les deux s'abstient. Sans amplitude sur un des trois horizons, s'abstient.

    Pression d'achat d'une barre : cloture moins le plus bas entre son plus bas et la cloture precedente.
    Moyenne sur n barres : somme des pressions sur somme des true ranges.
    UO = 100 x (4 x court + 2 x moyen + long) / 7. Reglages de Williams : 7, 14, 28, seuils 30 et 70.
    Intensite : profondeur au-dela du seuil, rapportee a la marge jusqu'a 0 ou 100.
    """

    def __init__(self, weight: Decimal, short: int, medium: int, long: int, lower: Decimal, upper: Decimal):
        self.name = f"UltimateOscillator({short},{medium},{long},{lower},{upper})"
        self.weight = weight
        self.warmup = long + 1
        self.short = short
        self.medium = medium
        self.long = long
        self.lower = lower
        self.upper = upper

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.long - 1:]
        pressures = [bar.close - min(bar.low, prev.close) for prev, bar in zip(bars, bars[1:])]
        averages = []
        for period in (self.short, self.medium, self.long):
            ranges = period * view.volatility(period)
            if ranges == 0:
                return None
            averages.append(sum(pressures[-period:], Decimal(0)) / ranges)
        oscillator = 100 * (4 * averages[0] + 2 * averages[1] + averages[2]) / 7
        if oscillator < self.lower:
            return Vote(1, (self.lower - oscillator) / self.lower)
        if oscillator > self.upper:
            return Vote(-1, (oscillator - self.upper) / (100 - self.upper))
        return None
