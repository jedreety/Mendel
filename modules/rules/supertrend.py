from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Supertrend(Rule):
    """Supertrend : bandes a `multiplier` unites de volatilite (`period` barres) autour du milieu de barre,
    qui ne reculent pas tant que la cloture precedente les respecte. La tendance devient baissiere quand la
    cloture passe sous la bande basse precedente, haussiere au-dessus de la bande haute precedente.
    Haussiere +1, baissiere -1.

    La serie porte sur une fenetre fixe de 3 x period + 1 barres et part dans le sens de la cloture par rapport
    au milieu de sa premiere barre : le vote ne depend pas de la taille de la vue.
    Intensite : distance entre la cloture et la bande active, en unites de volatilite, plafonnee a 1.
    """

    def __init__(self, weight: Decimal, period: int, multiplier: Decimal):
        self.name = f"Supertrend({period},{multiplier})"
        self.weight = weight
        self.warmup = 3 * period + 1
        self.period = period
        self.multiplier = multiplier

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.warmup:]
        upper = lower = rising = None
        for i in range(self.period, len(bars)):
            bar, prev = bars[i], bars[i - 1]
            volatility = View(view.symbol, bars[:i + 1]).volatility(self.period)
            middle = (bar.high + bar.low) / 2
            basic_upper = middle + self.multiplier * volatility
            basic_lower = middle - self.multiplier * volatility
            if rising is None:
                upper, lower, rising = basic_upper, basic_lower, bar.close >= middle
                continue
            if rising and bar.close < lower:
                rising = False
            elif not rising and bar.close > upper:
                rising = True
            upper = basic_upper if basic_upper < upper or prev.close > upper else upper
            lower = basic_lower if basic_lower > lower or prev.close < lower else lower
        if volatility == 0:
            return None
        band = lower if rising else upper
        return Vote(1 if rising else -1, min(Decimal(1), abs(bars[-1].close - band) / volatility))
