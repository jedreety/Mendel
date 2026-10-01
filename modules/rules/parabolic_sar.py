from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class ParabolicSar(Rule):
    """SAR parabolique de Wilder : tendance haussiere +1, baissiere -1.

    Pas d'acceleration `step`, plafonne a `maximum` (0.02 et 0.2 chez Wilder). Le SAR ne depasse jamais les
    extremes des deux barres precedentes, ni, au retournement, ceux de la barre courante et de la precedente.
    La serie part d'une fenetre fixe de 50 barres, dans le sens de la variation de cloture des deux premieres :
    le vote ne depend pas de la taille de la vue.
    Intensite : distance entre la cloture et le SAR en unites de volatilite (10 barres), plafonnee a 1.
    """

    WINDOW = 50
    REF = 10

    def __init__(self, weight: Decimal, step: Decimal, maximum: Decimal):
        self.name = f"ParabolicSar({step},{maximum})"
        self.weight = weight
        self.warmup = self.WINDOW
        self.step = step
        self.maximum = maximum

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.WINDOW:]
        rising = bars[1].close >= bars[0].close
        sar = bars[0].low if rising else bars[0].high
        extreme = bars[0].high if rising else bars[0].low
        acceleration = self.step
        for i in range(1, len(bars)):
            bar, prev, earlier = bars[i], bars[i - 1], bars[max(i - 2, 0):i]
            sar += acceleration * (extreme - sar)
            if rising:
                sar = min(sar, *(b.low for b in earlier))
                if bar.low <= sar:
                    rising, sar, extreme, acceleration = False, max(extreme, bar.high, prev.high), bar.low, self.step
                elif bar.high > extreme:
                    extreme, acceleration = bar.high, min(acceleration + self.step, self.maximum)
            else:
                sar = max(sar, *(b.high for b in earlier))
                if bar.high >= sar:
                    rising, sar, extreme, acceleration = True, min(extreme, bar.low, prev.low), bar.high, self.step
                elif bar.low < extreme:
                    extreme, acceleration = bar.low, min(acceleration + self.step, self.maximum)
        r = view.volatility(self.REF)
        if r == 0:
            return None
        return Vote(1 if rising else -1, min(Decimal(1), abs(bars[-1].close - sar) / r))
